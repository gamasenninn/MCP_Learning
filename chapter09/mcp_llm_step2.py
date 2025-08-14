"""
Step 2: LLM統合の準備
ツール情報をLLMが理解しやすい形式に整形
"""
import json
from typing import Dict, List, Any

class LLMIntegrationPrep:
    """LLM統合のための準備クラス"""
    
    def prepare_tools_for_llm(self, tools_schema: Dict[str, List[Any]]) -> str:
        """ツール情報をLLM用に整形
        
        重要なポイント：
        1. 各ツールの役割を明確に記述
        2. パラメータの型と必須/オプションを明示
        3. 具体的な使用例を提供
        """
        tools_description = []
        
        for server_name, tools in tools_schema.items():
            for tool in tools:
                # パラメータの詳細説明を生成
                params_desc = self._format_parameters(tool.get('parameters', {}))
                
                tool_desc = f"""
{server_name}.{tool['name']}:
  説明: {tool['description']}
  {params_desc}
"""
                tools_description.append(tool_desc.strip())
        
        return "\n\n".join(tools_description)
    
    def _format_parameters(self, params_schema: Dict) -> str:
        """パラメータ情報を読みやすく整形"""
        if not params_schema or 'properties' not in params_schema:
            return "パラメータ: なし"
        
        param_lines = ["パラメータ:"]
        properties = params_schema.get('properties', {})
        required = params_schema.get('required', [])
        
        for key, value in properties.items():
            param_type = value.get('type', 'any')
            param_desc = value.get('description', '')
            is_required = key in required
            
            # 型情報と必須/オプションを明確に表示
            req_text = "必須" if is_required else "オプション"
            line = f"    - {key} ({param_type}, {req_text}): {param_desc}"
            param_lines.append(line)
        
        return "\n".join(param_lines)
    
    def create_tool_selection_prompt(self, query: str, tools_desc: str) -> str:
        """効果的なツール選択プロンプトを生成
        
        プロンプト設計の重要点：
        1. 明確な指示
        2. 出力形式の固定
        3. 推論過程の記録
        """
        return f"""
あなたは優秀なアシスタントです。ユーザーの要求を分析し、適切なMCPツールを選択してください。

## ユーザーの要求
{query}

## 利用可能なツール
{tools_desc}

## 指示
1. ユーザーの要求を注意深く分析してください
2. 最も適切なツールを選択してください
3. 必要なパラメータを決定してください
4. パラメータの型に注意してください（numberは数値、stringは文字列）

## 出力形式
以下のJSON形式で応答してください（JSONのみ、説明文は不要）：
{{
  "server": "サーバー名",
  "tool": "ツール名",
  "arguments": {{
    "パラメータ名": 値
  }},
  "reasoning": "なぜこのツールを選んだか（簡潔に）"
}}

## 例
ユーザー: "100と250を足して"
応答:
{{
  "server": "calculator",
  "tool": "add",
  "arguments": {{"a": 100, "b": 250}},
  "reasoning": "数値の加算が要求されているため"
}}
"""
    
    def validate_llm_response(self, response: str) -> Dict:
        """LLMの応答を検証
        
        エラーハンドリング：
        1. JSON形式の検証
        2. 必須フィールドの確認
        3. 型の検証
        """
        try:
            # JSONパース
            result = json.loads(response)
            
            # needs_toolフィールドの確認
            if "needs_tool" not in result:
                raise ValueError("必須フィールド 'needs_tool' が見つかりません")
            
            # needs_toolの値に応じて必須フィールドを確認
            if result.get("needs_tool", False):
                # ツール実行の場合
                required_fields = ["server", "tool", "arguments"]
                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"ツール実行時の必須フィールド '{field}' が見つかりません")
            else:
                # 直接応答の場合
                if "response" not in result:
                    raise ValueError("直接応答時の必須フィールド 'response' が見つかりません")
            
            return result
            
        except json.JSONDecodeError as e:
            # JSON形式でない場合、テキストから抽出を試みる
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            raise ValueError(f"LLMの応答をパースできません: {e}")

# デモンストレーション
async def demonstrate_prep():
    """準備プロセスのデモ"""
    from mcp_llm_step1 import ToolCollector
    import asyncio
    
    # Step 1のツール収集を実行
    collector = ToolCollector()
    await collector.collect_all_tools()
    
    # Step 2の準備
    prep = LLMIntegrationPrep()
    
    # ツール情報をLLM用に整形
    tools_desc = prep.prepare_tools_for_llm(collector.tools_schema)
    print("📝 LLM用に整形されたツール情報:")
    print(tools_desc[:500] + "...")  # 最初の500文字を表示
    
    # プロンプトの例
    query = "東京の天気を教えて"
    prompt = prep.create_tool_selection_prompt(query, tools_desc)
    print("\n📋 生成されたプロンプト:")
    print(prompt[:800] + "...")  # 最初の800文字を表示

if __name__ == "__main__":
    import asyncio
    asyncio.run(demonstrate_prep())