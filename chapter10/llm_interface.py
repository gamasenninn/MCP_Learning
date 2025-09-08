#!/usr/bin/env python3
"""
LLM通信統一インターフェース
全クラスのLLM通信を統一管理し、テスタビリティとメンテナンス性を向上
"""

import json
import re
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI

from config_manager import Config
from utils import Logger, safe_str


class LLMInterface:
    """全LLM通信の統一インターフェース"""
    
    def __init__(self, config: Config, logger: Logger):
        """
        初期化
        
        Args:
            config: 設定オブジェクト
            logger: ロガー
        """
        self.config = config
        self.logger = logger
        self.client = AsyncOpenAI()
    
    def _get_llm_params(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """LLM呼び出しパラメータを統一生成"""
        params = {
            "model": self.config.llm.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.llm.temperature),
        }
        
        # GPT-5系モデルのreasoningサポート
        if hasattr(self.config.llm, "reasoning_effort") and "gpt-5" in params["model"]:
            params["reasoning_effort"] = self.config.llm.reasoning_effort
            
        # トークン数制限
        if hasattr(self.config.llm, "max_completion_tokens"):
            params["max_completion_tokens"] = self.config.llm.max_completion_tokens
            
        # JSONレスポンス形式指定
        if kwargs.get("response_format"):
            params["response_format"] = kwargs["response_format"]
            
        return params
    
    async def _call_llm(self, messages: List[Dict], **kwargs) -> str:
        """
        LLM呼び出しの共通処理
        
        Args:
            messages: メッセージリスト
            **kwargs: 追加パラメータ
            
        Returns:
            LLM応答テキスト
        """
        params = self._get_llm_params(messages, **kwargs)
        response = await self.client.chat.completions.create(**params)
        return safe_str(response.choices[0].message.content)
    
    async def determine_execution_type(self, user_query: str, recent_context: str, tools_info: str) -> Dict:
        """
        実行方式判定（MCPAgent用）
        
        Args:
            user_query: ユーザークエリ
            recent_context: 最近の会話履歴
            tools_info: 利用可能ツール情報
            
        Returns:
            実行方式判定結果
        """
        prompt = f"""あなたはユーザーからの要求を分析し、次のどの実行方式が最適かを判定するAIです。

利用可能ツール一覧:
{tools_info}

最近の会話履歴:
{recent_context}

現在のユーザー要求:
「{user_query}」

この要求に対して最適な処理方式を選択してください。

判定ルール:
1. 計算、データベース検索、API呼び出し、ファイル操作などが必要な場合 → TOOL
2. ユーザーの要求が曖昧で詳細確認が必要 → CLARIFICATION
3. 単純な質問で既存の知識だけで十分回答可能 → NO_TOOL

特に注意:
- 数値計算（足し算、引き算、掛け算、割り算）→ 必ずTOOL（計算ツールを使用）
- データ表示、検索、SQL関連 → 必ずTOOL（データベースツールを使用）
- ファイルの読み書き → 必ずTOOL（ファイルシステムツールを使用）

結果をJSON形式で返してください:
{{"type": "NO_TOOL|CLARIFICATION|TOOL", "reason": "判定理由", "response": "ユーザーへの応答", "clarification": {{"question": "追加質問"}}}}

- NO_TOOLの場合: "response"フィールドに自然で適切な日本語応答を含める
- CLARIFICATIONの場合: "clarification"フィールドに質問を含める
- TOOLの場合: "response"フィールドは省略可能"""

        try:
            content = await self._call_llm(
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(content)
            
            # type値の正規化
            if result.get('type') not in ['NO_TOOL', 'CLARIFICATION']:
                result['type'] = 'TOOL'
            
            self.logger.ulog(f"判定: {result.get('type', 'UNKNOWN')} - {result.get('reason', '')}", "info:classification", show_level=True)
            
            return result
            
        except Exception as e:
            self.logger.ulog(f"実行方式判定失敗: {e}", "error:error")
            return {"type": "TOOL", "reason": "判定エラーによりデフォルト選択"}
    
    async def generate_task_list(self, user_query: str, context: str, tools_info: str, custom_instructions: str = "") -> List[Dict]:
        """
        タスクリスト生成（MCPAgent用）
        
        Args:
            user_query: ユーザークエリ
            context: 会話コンテキスト
            tools_info: ツール情報
            custom_instructions: カスタム指示
            
        Returns:
            生成されたタスクリスト
        """
        prompt = f"""あなたは以下のタスクを遂行するAIアシスタントです：

ユーザーリクエスト: {user_query}
{custom_instructions}

利用可能ツール:
{tools_info}

会話履歴とコンテキスト:
{context}

上記のユーザーリクエストを実行するために必要なタスクを順序立ててリストアップしてください。
各タスクはJSON形式で、以下の要素を含める必要があります：
- tool: 使用するツール名
- params: ツールに渡すパラメータ（辞書形式）
- description: タスクの説明

応答は純粋なJSONリスト形式でお願いします：
[
  {{"tool": "ツール名", "params": {{"param1": "value1"}}, "description": "タスクの説明"}},
  ...
]"""

        try:
            content = await self._call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # JSONリストとして解析を試行
            try:
                tasks = json.loads(content)
                if isinstance(tasks, list):
                    return tasks
            except json.JSONDecodeError:
                pass
            
            # JSONブロック抽出を試行
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                tasks = json.loads(json_match.group(1))
                if isinstance(tasks, list):
                    return tasks
            
            # フォールバック: 単一タスクとして処理
            self.logger.ulog(f"タスクリスト解析失敗、フォールバック実行: {content[:100]}...", "warning:task")
            return []
            
        except Exception as e:
            self.logger.ulog(f"タスクリスト生成失敗: {e}", "error:task")
            return []
    
    async def interpret_results(self, user_query: str, results: List[Dict], context: str, custom_instructions: str = "") -> str:
        """
        実行結果解釈（MCPAgent用）
        
        Args:
            user_query: ユーザークエリ
            results: ツール実行結果リスト
            context: 会話コンテキスト
            custom_instructions: カスタム指示
            
        Returns:
            解釈された結果テキスト
        """
        prompt = f"""以下のユーザーリクエストに対するツール実行結果を解釈して、自然な日本語で回答してください。

ユーザーリクエスト: {user_query}
{custom_instructions}

ツール実行結果:
{json.dumps(results, ensure_ascii=False, indent=2)}

会話コンテキスト:
{context}

実行結果を基に、ユーザーにとって理解しやすい形で回答を作成してください。"""

        try:
            return await self._call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
        except Exception as e:
            self.logger.ulog(f"結果解釈失敗: {e}", "error:interpretation")
            return f"実行は完了しましたが、結果の解釈中にエラーが発生しました: {str(e)}"
    
    async def resolve_task_parameters(self, task_dict: Dict, context: List[Dict], tools_info: str, user_query: str) -> Dict:
        """
        タスクパラメータ解決（TaskExecutor用）
        
        Args:
            task_dict: タスク情報辞書
            context: 実行コンテキスト
            tools_info: ツール情報
            user_query: ユーザークエリ
            
        Returns:
            解決されたパラメータ辞書
        """
        prompt = f"""以下のタスクのパラメータを解決してください：

ユーザーリクエスト: {user_query}
タスク: {task_dict.get('description', '')}
現在のパラメータ: {json.dumps(task_dict.get('params', {}), ensure_ascii=False)}

実行コンテキスト:
{json.dumps(context, ensure_ascii=False, indent=2)}

利用可能ツール情報:
{tools_info}

パラメータに前の実行結果の参照（例："{{前の結果}}"）がある場合は、実行コンテキストから適切な値に置換してください。

応答はJSON形式でお願いします：
```json
{{"resolved_params": {{解決されたパラメータ}}, "reasoning": "解決の理由"}}
```"""

        try:
            content = await self._call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # JSONブロック抽出
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1).strip())
                resolved_params = result.get("resolved_params", task_dict.get('params', {}))
                reasoning = result.get("reasoning", "")
                
                if reasoning:
                    self.logger.ulog(f"{reasoning}", "info:param", show_level=True)
                
                return resolved_params
            else:
                # JSONブロックがない場合、直接解析を試行
                result = json.loads(content)
                return result.get("resolved_params", task_dict.get('params', {}))
                
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.ulog(f"パラメータ解決に失敗、元の値を使用: {e}", "warning:param")
            return task_dict.get('params', {})
        except Exception as e:
            self.logger.ulog(f"パラメータ解決エラー: {e}", "error:param")
            return task_dict.get('params', {})
    
    async def fix_error_parameters(self, tool: str, params: Dict, error_msg: str, tools_info: str, user_query: str = "") -> Optional[Dict]:
        """
        エラーパラメータ修正（ErrorHandler用）
        
        Args:
            tool: ツール名
            params: エラーが発生したパラメータ
            error_msg: エラーメッセージ
            tools_info: ツール情報
            user_query: ユーザークエリ
            
        Returns:
            修正されたパラメータ、修正不可能な場合はNone
        """
        prompt = f"""以下のツール実行エラーを分析し、パラメータを修正してください：

ツール名: {tool}
エラーパラメータ: {json.dumps(params, ensure_ascii=False, indent=2)}
エラーメッセージ: {error_msg}
ユーザークエリ: {user_query}

利用可能ツール情報:
{tools_info}

エラーメッセージを分析してパラメータの問題を特定し、修正可能であれば修正してください。

修正成功の場合：
```json
{{"修正成功": true, "params": {{修正されたパラメータ}}}}
```

修正不可能な場合：
```json
{{"修正成功": false, "理由": "修正できない理由"}}
```"""

        try:
            content = await self._call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # JSONブロック抽出
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                if result.get("修正成功"):
                    self.logger.ulog(f"パラメータを自動修正: {result.get('params')}", "info:correction")
                    return result.get("params")
            
            self.logger.ulog(f"LLM応答の解析に失敗: {content[:100]}...", "error:correction")
            return None
            
        except Exception as e:
            self.logger.ulog(f"パラメータ修正エラー: {e}", "error:correction")
            return None
    
    async def generate_error_recovery_plan(self, error_context: Dict, user_query: str, tools_info: str) -> Dict:
        """
        エラー回復戦略生成（ErrorHandler用）
        
        Args:
            error_context: エラー情報コンテキスト
            user_query: ユーザークエリ
            tools_info: ツール情報
            
        Returns:
            回復戦略辞書
        """
        prompt = f"""以下のエラー状況を分析し、回復戦略を提案してください：

ユーザーリクエスト: {user_query}
エラー情報: {json.dumps(error_context, ensure_ascii=False, indent=2)}

利用可能ツール情報:
{tools_info}

エラーの原因を分析し、以下の回復戦略を提案してください：
1. 自動修正の可能性
2. 代替手段の提案
3. ユーザーへの追加情報要求

JSON形式で回答してください：
```json
{{"strategy": "auto_retry|alternative|clarification", "action": "具体的なアクション", "reason": "理由"}}
```"""

        try:
            content = await self._call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1).strip())
            else:
                return json.loads(content)
                
        except Exception as e:
            self.logger.ulog(f"回復戦略生成エラー: {e}", "error:recovery")
            return {"strategy": "manual", "action": "手動対応が必要", "reason": f"戦略生成失敗: {str(e)}"}
    
    async def judge_tool_execution_result(self, prompt: str) -> Dict:
        """
        ツール実行結果の判断（TaskExecutor用）
        
        Args:
            prompt: 判断用プロンプト
            
        Returns:
            判断結果
        """
        try:
            content = await self._call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(content)
            
            # 必要なフィールドのデフォルト値設定
            if "is_success" not in result:
                result["is_success"] = True
            if "needs_retry" not in result:
                result["needs_retry"] = False
            if "processed_result" not in result:
                result["processed_result"] = "処理結果を確認しました"
            
            return result
            
        except Exception as e:
            self.logger.ulog(f"ツール実行結果判断エラー: {e}", "error:judgment")
            return {
                "is_success": True,
                "needs_retry": False,
                "processed_result": "判断エラーのため成功として処理",
                "summary": f"判断エラー: {str(e)}"
            }