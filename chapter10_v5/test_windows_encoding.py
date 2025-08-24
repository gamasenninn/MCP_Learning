#!/usr/bin/env python3
"""
Windows環境でのエンコーディング処理テスト

修正前後での絵文字・特殊文字処理を確認する
"""

import sys
import os

def test_encoding():
    """エンコーディングテストの実行"""
    
    print("=" * 60)
    print("Windows Encoding Test")
    print("=" * 60)
    print(f"Platform: {sys.platform}")
    print(f"Default encoding: {sys.getdefaultencoding()}")
    
    # 環境情報
    if hasattr(sys.stdout, 'encoding'):
        print(f"stdout encoding: {sys.stdout.encoding}")
        if hasattr(sys.stdout, 'errors'):
            print(f"stdout errors mode: {sys.stdout.errors}")
    
    print("=" * 60)

    # テストケース：よくある絵文字・特殊文字
    test_cases = [
        "通常のテキスト",
        "✅ 成功マーク",
        "❌ 失敗マーク", 
        "🚀 ロケット絵文字",
        "💡 電球アイデア",
        "⚠️ 警告マーク",
        "📋 クリップボード",
        "🔴 赤丸",
        "🟡 黄丸",
        "🟢 緑丸",
        "温度: 25°C",
        "北京（Beijing）中国語",
        "東京都新宿区",
        "範囲: α～ω",
        "数学: ∑∏∫",
        "記号: ←→↑↓",
        "矢印: ⬅️➡️⬆️⬇️",
        "チェック: ☑️✔️",
        "星: ⭐🌟",
        "ハート: ❤️💙💚",
    ]

    # 各テストケースを実行
    for i, text in enumerate(test_cases, 1):
        print(f"\nTest {i:2d}: ", end="", flush=True)
        
        # 表示テスト
        try:
            print(f"'{text}'", end=" -> ", flush=True)
            
            # cp932エンコード可能性チェック
            try:
                text.encode('cp932')
                print("[cp932:OK]", end="")
            except UnicodeEncodeError as e:
                print("[cp932:NG]", end="")
                
                # errors='replace'での結果確認
                safe_text = text.encode('cp932', errors='replace').decode('cp932')
                print(f" Safe:'{safe_text}'", end="")
            
            print()  # 改行
            
        except Exception as e:
            print(f" [ERROR: {e}]")

def test_mcp_response_simulation():
    """MCPサーバーからの応答をシミュレート"""
    
    print("\n" + "=" * 60)
    print("MCP Response Simulation Test")
    print("=" * 60)
    
    # よくあるMCPサーバーからの応答例
    mock_responses = [
        "タスクが完了しました ✅",
        "エラーが発生しました ❌",  
        "処理を開始しています 🚀",
        "天気: 晴れ ☀️ 温度: 25°C",
        "計算結果: √16 = 4",
        "データベース接続完了 💾",
        "警告: メモリ不足 ⚠️",
        "北京の現在温度: 22°C 🌡️",
        "[OK] ✅ タスクリスト生成完了",
        "🔍 検索結果: 10件見つかりました",
    ]
    
    for i, response in enumerate(mock_responses, 1):
        print(f"\nMock Response {i:2d}: ", end="")
        
        # Windows環境での処理をシミュレート
        if sys.platform == "win32":
            try:
                # cp932エンコード可能かチェック
                response.encode('cp932')
                print(f"'{response}' [OK]")
            except UnicodeEncodeError:
                # errors='replace'で修正
                safe_response = response.encode('cp932', errors='replace').decode('cp932')
                print(f"'{response}' -> '{safe_response}' [FIXED]")
        else:
            print(f"'{response}' [Non-Windows]")

def test_print_functionality():
    """print文の動作確認"""
    
    print("\n" + "=" * 60)
    print("Print Function Test")
    print("=" * 60)
    
    dangerous_texts = [
        "✅ これはテストです",
        "🚀 ロケット発射！",
        "❌ エラー発生",
        "💡 ひらめき！",
        "⚠️ 注意してください"
    ]
    
    print("\n直接print()テスト:")
    for text in dangerous_texts:
        try:
            print(f"  - {text}")
        except Exception as e:
            print(f"  - [ERROR] {e}")
    
    print("\n修正後のsys.stdoutでのテスト完了:")
    print("  すべてのテキストが表示されていれば修正成功です")

def main():
    """メイン実行"""
    try:
        test_encoding()
        test_mcp_response_simulation() 
        test_print_functionality()
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print("✓ エンコーディングテスト完了")
        print("✓ MCPレスポンステスト完了") 
        print("✓ print機能テスト完了")
        print("\nもしエラーが発生していない場合、修正は成功です！")
        print("絵文字が ? に変換されているのは正常な動作です。")
        
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        print("修正が必要な可能性があります。")

if __name__ == "__main__":
    main()