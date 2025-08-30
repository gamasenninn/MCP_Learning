#!/usr/bin/env python3
"""
GPT-5 Interactive Chat Program
GPT-5シリーズとの対話型プログラム - 推論制御とverbosity制御付き
"""

import asyncio
import os
import time
from pathlib import Path
from openai import AsyncOpenAI

def load_env():
    """環境変数読み込み"""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

class GPT5Chat:
    """GPT-5対話クラス"""
    
    def __init__(self):
        self.client = AsyncOpenAI()
        self.conversation = []
        self.settings = {
            "model": "gpt-5-mini",
            "reasoning_effort": "minimal",  # デフォルトは高速モード
            "verbosity": "medium",
            "max_completion_tokens": 5000
        }
        
    def show_settings(self):
        """現在の設定を表示"""
        print(f"\n=== 現在の設定 ===")
        print(f"モデル: {self.settings['model']}")
        print(f"推論レベル: {self.settings['reasoning_effort']}")
        print(f"詳細度: {self.settings['verbosity']}")
        print(f"最大トークン: {self.settings['max_completion_tokens']}")
        print("=" * 30)
    
    def show_help(self):
        """ヘルプを表示"""
        print("""
=== GPT-5 Chat コマンド ===
/help          : このヘルプを表示
/settings      : 現在の設定を表示
/model <name>  : モデル変更 (gpt-5-mini, gpt-5-nano, gpt-5, gpt-4o-mini)
/reasoning <level> : 推論レベル変更 (minimal, low, medium, high)
/verbosity <level> : 詳細度変更 (low, medium, high)
/tokens <num>  : 最大トークン数変更
/clear         : 会話履歴をクリア
/quit          : 終了

=== 推論レベル説明 ===
minimal : 推論なし - 高速応答 (翻訳、要約、分類など)
low     : 少しの推論 - バランス
medium  : 標準推論 - 一般的な質問
high    : 深い推論 - 複雑な問題解決

通常の会話は直接入力してください。
""")
    
    async def send_message(self, user_input: str):
        """メッセージ送信と応答受信"""
        
        # 会話履歴に追加
        self.conversation.append({"role": "user", "content": user_input})
        
        try:
            start_time = time.time()
            
            # モデル別のパラメータ設定
            params = {
                "model": self.settings["model"],
                "messages": self.conversation
            }
            
            # GPT-5シリーズの場合
            if self.settings["model"].startswith("gpt-5"):
                params["max_completion_tokens"] = self.settings["max_completion_tokens"]
                params["reasoning_effort"] = self.settings["reasoning_effort"]
                params["verbosity"] = self.settings["verbosity"]
            else:
                # GPT-4シリーズの場合
                params["max_tokens"] = self.settings["max_completion_tokens"]
                params["temperature"] = 0.7
            
            response = await self.client.chat.completions.create(**params)
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # 応答を取得
            content = response.choices[0].message.content
            self.conversation.append({"role": "assistant", "content": content})
            
            # 応答表示
            print(f"\nGPT-5: {content}")
            
            # 統計情報表示
            if response.usage:
                usage = response.usage
                reasoning_tokens = 0
                if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                    details = usage.completion_tokens_details
                    reasoning_tokens = getattr(details, 'reasoning_tokens', 0)
                
                print(f"\n--- 統計 ---")
                print(f"応答時間: {response_time:.2f}秒")
                print(f"トークン: {usage.prompt_tokens} + {usage.completion_tokens} = {usage.total_tokens}")
                if reasoning_tokens > 0:
                    print(f"推論トークン: {reasoning_tokens}")
                print(f"終了理由: {response.choices[0].finish_reason}")
            
            return True
            
        except Exception as e:
            print(f"エラー: {e}")
            return False
    
    def process_command(self, command: str):
        """コマンド処理"""
        parts = command.strip().split()
        cmd = parts[0].lower()
        
        if cmd == "/help":
            self.show_help()
        elif cmd == "/settings":
            self.show_settings()
        elif cmd == "/clear":
            self.conversation = []
            print("会話履歴をクリアしました。")
        elif cmd == "/model" and len(parts) > 1:
            model = parts[1]
            if model in ["gpt-5-mini", "gpt-5-nano", "gpt-5", "gpt-4o-mini"]:
                self.settings["model"] = model
                print(f"モデルを {model} に変更しました。")
            else:
                print("使用可能モデル: gpt-5-mini, gpt-5-nano, gpt-5, gpt-4o-mini")
        elif cmd == "/reasoning" and len(parts) > 1:
            level = parts[1]
            if level in ["minimal", "low", "medium", "high"]:
                self.settings["reasoning_effort"] = level
                print(f"推論レベルを {level} に変更しました。")
            else:
                print("使用可能レベル: minimal, low, medium, high")
        elif cmd == "/verbosity" and len(parts) > 1:
            level = parts[1]
            if level in ["low", "medium", "high"]:
                self.settings["verbosity"] = level
                print(f"詳細度を {level} に変更しました。")
            else:
                print("使用可能レベル: low, medium, high")
        elif cmd == "/tokens" and len(parts) > 1:
            try:
                tokens = int(parts[1])
                if 50 <= tokens <= 4000:
                    self.settings["max_completion_tokens"] = tokens
                    print(f"最大トークン数を {tokens} に変更しました。")
                else:
                    print("トークン数は50-4000の範囲で指定してください。")
            except ValueError:
                print("数値を入力してください。")
        elif cmd == "/quit":
            return False
        else:
            print("不明なコマンドです。/help でコマンド一覧を確認してください。")
        
        return True

async def main():
    """メイン実行関数"""
    load_env()
    
    print("=== GPT-5 Interactive Chat ===")
    print("GPT-5シリーズとの対話プログラム")
    print("コマンドは / で始まります。/help でヘルプを表示。")
    print("Ctrl+C または /quit で終了。")
    print()
    
    chat = GPT5Chat()
    chat.show_settings()
    
    try:
        while True:
            user_input = input("\nあなた: ").strip()
            
            if not user_input:
                continue
            
            if user_input.startswith('/'):
                # コマンド処理
                if not chat.process_command(user_input):
                    break
            else:
                # 通常の会話
                success = await chat.send_message(user_input)
                if not success:
                    print("メッセージの送信に失敗しました。再試行してください。")
    
    except KeyboardInterrupt:
        print("\n\nチャットを終了します。")
    except Exception as e:
        print(f"\n予期しないエラー: {e}")

if __name__ == "__main__":
    asyncio.run(main())