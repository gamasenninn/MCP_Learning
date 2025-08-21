"""
Step 2: LLM統合の準備 (V2 - mcpServers形式対応)
ツール情報をLLMが理解しやすい形式に整形
"""
import json
from typing import Dict, List, Any

class LLMIntegrationPrepV2:
    """LLM統合のための準備クラス（mcpServers形式対応）"""
    
    def prepare_tools_for_llm(self, tools_schema: Dict[str, List[Any]]) -> str:
        """ツール情報をLLM用に整形
        
        重要なポイント：
        1. 各ツールの役割を明確に記述
        2. パラメータの型と必須/オプションを明示
        3. 具体的な使用例を提供
        4. mcpServers形式のツール情報を適切に処理
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
    
    def _format_parameters(self, parameters: Dict) -> str:
        """パラメータ情報を読みやすく整形（V2形式対応）"""
        if not parameters:
            return "パラメータ: なし"
        
        param_lines = ["パラメータ:"]
        
        for key, value in parameters.items():
            param_type = value.get('type', 'any')
            param_desc = value.get('description', '')
            
            # V2形式では必須/オプションの判定を簡略化
            param_lines.append(f"    - {key} ({param_type}): {param_desc}")
        
        return "\n  ".join(param_lines)
    
    def create_tool_selection_prompt(self, user_query: str, tools_desc: str) -> str:
        """LLMにツール選択を依頼するプロンプトを作成"""
        return f"""あなたはMCPツール選択アシスタントです。

利用可能なツール:
{tools_desc}

ユーザーの要求: "{user_query}"

この要求に最適なツールを選択し、以下のJSON形式で応答してください：

{{
  "selected_tool": "サーバー名.ツール名",
  "parameters": {{
    "パラメータ名": "値"
  }},
  "reasoning": "選択理由"
}}

重要な注意点：
- 必ずJSON形式で応答してください
- 利用可能なツールから適切なものを選んでください
- パラメータの型と値に注意してください
- 数値が必要な場合は適切な数値型で指定してください"""
    
    def validate_llm_response(self, response_text: str) -> Dict:
        """LLMの応答を検証・パース"""
        try:
            # JSONデータを抽出（コードブロック形式の場合も対応）
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # コードブロック形式の場合、中身を取り出す
                lines = response_text.split('\n')
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        json_lines.append(line)
                response_text = '\n'.join(json_lines)
            
            parsed = json.loads(response_text)
            
            # 必要なキーの存在確認
            required_keys = ["selected_tool", "parameters", "reasoning"]
            for key in required_keys:
                if key not in parsed:
                    return {
                        "valid": False,
                        "error": f"必要なキー '{key}' が見つかりません"
                    }
            
            # ツール名の形式確認（サーバー名.ツール名）
            tool_name = parsed["selected_tool"]
            if "." not in tool_name:
                return {
                    "valid": False,
                    "error": "ツール名は 'サーバー名.ツール名' の形式である必要があります"
                }
            
            server_name, tool_name_part = tool_name.split(".", 1)
            
            return {
                "valid": True,
                "server_name": server_name,
                "tool_name": tool_name_part,
                "parameters": parsed["parameters"],
                "reasoning": parsed["reasoning"]
            }
            
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "error": f"JSON解析エラー: {str(e)}"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"予期しないエラー: {str(e)}"
            }
    
    def display_llm_integration_example(self):
        """LLM統合の例を表示"""
        print("🤖 LLM統合の例:")
        print("\nユーザー入力: '東京の天気を教えて'")
        print("\nLLMの応答例:")
        example_response = {
            "selected_tool": "weather.get_weather",
            "parameters": {
                "city": "Tokyo"
            },
            "reasoning": "ユーザーが東京の天気情報を求めているため、weather サーバーの get_weather ツールを使用します"
        }
        print(json.dumps(example_response, ensure_ascii=False, indent=2))
        
        print("\n✅ 検証結果: 有効な応答")
        validation = self.validate_llm_response(json.dumps(example_response))
        if validation["valid"]:
            print(f"   サーバー: {validation['server_name']}")
            print(f"   ツール: {validation['tool_name']}")
            print(f"   パラメータ: {validation['parameters']}")

# デモンストレーション用
if __name__ == "__main__":
    prep = LLMIntegrationPrepV2()
    
    # サンプルツールスキーマ（mcpServers形式対応）
    sample_schema = {
        "calculator": [
            {
                "name": "add",
                "description": "2つの数値を加算します",
                "parameters": {
                    "a": {"type": "number", "description": "第1の数値"},
                    "b": {"type": "number", "description": "第2の数値"}
                }
            }
        ],
        "weather": [
            {
                "name": "get_weather",
                "description": "指定した都市の天気情報を取得します",
                "parameters": {
                    "city": {"type": "string", "description": "都市名"}
                }
            }
        ]
    }
    
    print("🚀 LLM統合準備システム (V2 - mcpServers形式対応)")
    print("="*50)
    
    # ツール情報の整形例
    formatted = prep.prepare_tools_for_llm(sample_schema)
    print("\n📋 整形されたツール情報:")
    print(formatted)
    
    # LLM統合例の表示
    prep.display_llm_integration_example()