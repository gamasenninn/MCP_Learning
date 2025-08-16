#!/usr/bin/env python3
"""
インテリジェントエラーハンドラー
LLMを使用してエラーを分析し、自動的に修正案を生成
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import re
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from openai import AsyncOpenAI
from error_handler import BasicErrorHandler, ErrorContext, ErrorResolution, ErrorSeverity, ErrorCategory

@dataclass
class ErrorAnalysis:
    """LLMによるエラー分析結果"""
    cause: str                    # エラーの原因
    fix_suggestions: List[str]    # 修正案のリスト
    parameter_fixes: Dict[str, Any]  # パラメータの修正案
    alternative_tools: List[str]  # 代替ツールの提案
    confidence: float             # 分析の確信度（0-1）
    explanation: str              # 日本語での説明

class IntelligentErrorHandler(BasicErrorHandler):
    """LLMベースのインテリジェントエラーハンドラー"""
    
    def __init__(self, api_key: Optional[str] = None, verbose: bool = True):
        super().__init__(verbose)
        
        # OpenAI APIキーの取得
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI APIキーが設定されていません")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.analysis_cache = {}  # エラー分析のキャッシュ
        self.learning_history = []  # 学習履歴
        
    async def analyze_with_llm(
        self,
        error: Exception,
        task_context: Dict[str, Any]
    ) -> ErrorAnalysis:
        """LLMを使ってエラーを分析"""
        
        # キャッシュチェック
        cache_key = f"{type(error).__name__}:{str(error)[:100]}"
        if cache_key in self.analysis_cache:
            if self.verbose:
                print("[キャッシュ] 既知のエラーパターンを使用")
            return self.analysis_cache[cache_key]
        
        # プロンプトの構築
        prompt = self._build_analysis_prompt(error, task_context)
        
        try:
            # LLMに分析を依頼
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたはMCPエラー分析の専門家です。エラーを分析し、具体的な修正案を提供してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # レスポンスを解析
            analysis = self._parse_llm_response(response.choices[0].message.content)
            
            # キャッシュに保存
            self.analysis_cache[cache_key] = analysis
            
            # 学習履歴に追加
            self.learning_history.append({
                "error": str(error),
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            })
            
            return analysis
            
        except Exception as e:
            if self.verbose:
                print(f"[LLM分析エラー] {e}")
            
            # フォールバック分析
            return ErrorAnalysis(
                cause="LLM分析に失敗しました",
                fix_suggestions=["基本的なリトライを実行"],
                parameter_fixes={},
                alternative_tools=[],
                confidence=0.1,
                explanation="エラー分析に失敗したため、基本的な対処を行います"
            )
    
    def _build_analysis_prompt(self, error: Exception, task_context: Dict[str, Any]) -> str:
        """LLM用のプロンプトを構築"""
        prompt_parts = [
            "以下のエラーを分析し、JSON形式で修正案を提供してください。",
            "",
            "## エラー情報",
            f"エラータイプ: {type(error).__name__}",
            f"エラーメッセージ: {str(error)}",
            "",
            "## タスクコンテキスト",
            f"実行中のツール: {task_context.get('tool', '不明')}",
            f"パラメータ: {json.dumps(task_context.get('params', {}), ensure_ascii=False)}",
            f"サーバー: {task_context.get('server', '不明')}",
            ""
        ]
        
        # 利用可能なツールがある場合
        if task_context.get('available_tools'):
            prompt_parts.extend([
                "## 利用可能なツール",
                json.dumps(task_context.get('available_tools', []), ensure_ascii=False),
                ""
            ])
        
        prompt_parts.extend([
            "## 要求する出力形式（JSON）",
            "```json",
            "{",
            '  "cause": "エラーの原因（日本語）",',
            '  "fix_suggestions": ["修正案1", "修正案2"],',
            '  "parameter_fixes": {"パラメータ名": 具体的な値（数値または文字列）},',
            '  "alternative_tools": ["代替ツール1", "代替ツール2"],',
            '  "confidence": 0.8,',
            '  "explanation": "日本語での詳細な説明"',
            "}",
            "```",
            "",
            "重要: parameter_fixesには具体的な値を入れてください。説明文ではなく、実際に使用できる値（数値、文字列など）を指定してください。",
            "例: {'a': 100} や {'text': 'hello'} のように。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(self, response: str) -> ErrorAnalysis:
        """LLMレスポンスを解析"""
        try:
            # JSON部分を抽出
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 全体をJSONとして扱う
                json_str = response
            
            # JSONパース
            data = json.loads(json_str)
            
            return ErrorAnalysis(
                cause=data.get("cause", "不明"),
                fix_suggestions=data.get("fix_suggestions", []),
                parameter_fixes=data.get("parameter_fixes", {}),
                alternative_tools=data.get("alternative_tools", []),
                confidence=float(data.get("confidence", 0.5)),
                explanation=data.get("explanation", "分析結果なし")
            )
            
        except Exception as e:
            if self.verbose:
                print(f"[パースエラー] {e}")
            
            # パース失敗時のフォールバック
            return ErrorAnalysis(
                cause="レスポンス解析失敗",
                fix_suggestions=[],
                parameter_fixes={},
                alternative_tools=[],
                confidence=0.0,
                explanation=response[:200] if response else "なし"
            )
    
    async def suggest_fix(
        self,
        error: Exception,
        task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """エラーに対する修正案を提案"""
        
        if self.verbose:
            print("\n[AI分析] エラーを分析中...")
        
        # LLMで分析
        analysis = await self.analyze_with_llm(error, task_context)
        
        if self.verbose:
            print(f"  原因: {analysis.cause}")
            print(f"  確信度: {analysis.confidence:.1%}")
            if analysis.fix_suggestions:
                print(f"  修正案:")
                for i, suggestion in enumerate(analysis.fix_suggestions[:3], 1):
                    print(f"    {i}. {suggestion}")
        
        # 最適な修正戦略を決定
        fix_strategy = self._determine_fix_strategy(analysis, task_context)
        
        return {
            "analysis": analysis,
            "strategy": fix_strategy,
            "success": analysis.confidence > 0.5
        }
    
    def _determine_fix_strategy(
        self,
        analysis: ErrorAnalysis,
        task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """修正戦略を決定"""
        
        strategy = {
            "action": "retry",
            "modifications": {},
            "alternative": None
        }
        
        # パラメータ修正がある場合
        if analysis.parameter_fixes:
            strategy["action"] = "modify_and_retry"
            strategy["modifications"] = analysis.parameter_fixes
            if self.verbose:
                print(f"  パラメータ修正: {analysis.parameter_fixes}")
        
        # 代替ツールがある場合
        elif analysis.alternative_tools:
            available_tools = task_context.get('available_tools', [])
            for alt_tool in analysis.alternative_tools:
                if alt_tool in available_tools:
                    strategy["action"] = "use_alternative"
                    strategy["alternative"] = alt_tool
                    if self.verbose:
                        print(f"  代替ツール: {alt_tool}")
                    break
        
        # 確信度が低い場合はスキップ
        elif analysis.confidence < 0.3:
            strategy["action"] = "skip"
            if self.verbose:
                print("  確信度が低いためスキップを推奨")
        
        return strategy
    
    async def learn_from_success(
        self,
        error: Exception,
        fix_applied: Dict[str, Any],
        success: bool
    ):
        """成功した修正から学習"""
        
        if success:
            # 成功パターンをキャッシュに追加
            cache_key = f"SUCCESS:{type(error).__name__}:{str(error)[:50]}"
            self.analysis_cache[cache_key] = fix_applied
            
            if self.verbose:
                print(f"[学習] 成功パターンを記録しました")
    
    def get_learning_report(self) -> str:
        """学習レポートを生成"""
        
        report_lines = [
            "インテリジェントエラーハンドリング学習レポート",
            "=" * 60
        ]
        
        # キャッシュ統計
        report_lines.extend([
            "\n[キャッシュ統計]",
            f"  分析済みパターン: {len(self.analysis_cache)}",
            f"  学習履歴: {len(self.learning_history)}件"
        ])
        
        # 最近の学習
        if self.learning_history:
            report_lines.append("\n[最近の学習]")
            for entry in self.learning_history[-5:]:
                analysis = entry["analysis"]
                report_lines.append(f"  - {analysis.cause[:50]} (確信度: {analysis.confidence:.1%})")
        
        # エラーカテゴリ別の成功率
        if self.error_stats["total"] > 0:
            success_rate = (self.error_stats["resolved"] / self.error_stats["total"]) * 100
            report_lines.extend([
                "\n[AI支援による改善]",
                f"  全体解決率: {success_rate:.1f}%",
                f"  AIによる修正提案: {len(self.analysis_cache)}件"
            ])
        
        return "\n".join(report_lines)


# テスト関数
async def test_intelligent_handler():
    """インテリジェントエラーハンドラーのテスト"""
    
    print("インテリジェントエラーハンドラーのテスト")
    print("=" * 60)
    
    # APIキーチェック
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[警告] OPENAI_API_KEYが設定されていません")
        print("テストをスキップします")
        return
    
    handler = IntelligentErrorHandler(api_key=api_key)
    
    # テスト1: パラメータエラーの分析
    print("\n[テスト1] パラメータエラー")
    print("-" * 40)
    
    error1 = ValueError("Parameter 'a' must be a number, got 'abc'")
    context1 = {
        "tool": "add",
        "params": {"a": "abc", "b": 200},
        "server": "calculator",
        "available_tools": ["add", "subtract", "multiply", "divide"]
    }
    
    fix1 = await handler.suggest_fix(error1, context1)
    print(f"\n分析結果:")
    print(f"  {fix1['analysis'].explanation}")
    
    # テスト2: ツール不在エラー
    print("\n[テスト2] ツール不在エラー")
    print("-" * 40)
    
    error2 = AttributeError("Tool 'calculate_tax' not found")
    context2 = {
        "tool": "calculate_tax",
        "params": {"amount": 1000, "rate": 0.1},
        "server": "calculator",
        "available_tools": ["add", "subtract", "multiply", "divide"]
    }
    
    fix2 = await handler.suggest_fix(error2, context2)
    print(f"\n分析結果:")
    print(f"  {fix2['analysis'].explanation}")
    
    # テスト3: 複雑な計算エラー
    print("\n[テスト3] ゼロ除算エラー")
    print("-" * 40)
    
    error3 = ZeroDivisionError("division by zero")
    context3 = {
        "tool": "divide",
        "params": {"a": 100, "b": 0},
        "server": "calculator"
    }
    
    fix3 = await handler.suggest_fix(error3, context3)
    print(f"\n分析結果:")
    print(f"  {fix3['analysis'].explanation}")
    
    # 学習レポート
    print("\n" + "=" * 60)
    print(handler.get_learning_report())


if __name__ == "__main__":
    asyncio.run(test_intelligent_handler())