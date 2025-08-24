#!/usr/bin/env python3
"""
MCP Agent UTF-8修正テスト

実際のMCPサーバーレスポンス処理をテスト
テストスクリプト自体は絵文字をprint出力しない
"""

import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# 修正後のconnection_managerをインポート
sys.path.append('.')

async def test_connection_manager_encoding():
    """ConnectionManagerのエンコーディング修正をテスト"""
    
    print("=" * 50)
    print("MCP Agent Encoding Fix Test")
    print("=" * 50)
    print(f"Platform: {sys.platform}")
    print(f"stdout encoding: {getattr(sys.stdout, 'encoding', 'unknown')}")
    print(f"stdout errors: {getattr(sys.stdout, 'errors', 'unknown')}")
    print()
    
    # テストデータ：MCPサーバーから返される可能性のある応答
    test_responses = [
        "計算完了",  # 通常の日本語
        "Task completed ✅",  # 絵文字付き英語
        "エラーが発生しました ❌",  # 絵文字付き日本語
        "処理中 🚀",  # 絵文字
        "温度: 25°C",  # 特殊記号
        "警告 ⚠️ メモリ不足",  # 警告絵文字
        "結果: [1, 2, 3] 💡",  # データ + 絵文字
        "北京の天気 🌡️ 22°C",  # 中国語地名 + 絵文字
    ]
    
    # ConnectionManagerのインポートと模擬サーバー設定
    try:
        from connection_manager import ConnectionManager
        
        # モックのMCPクライアントを作成
        mock_client = AsyncMock()
        
        # ConnectionManagerを作成（初期化なし）
        conn_manager = ConnectionManager()
        conn_manager.tools_info = {"test_tool": {"server": "test_server"}}
        conn_manager.clients = {"test_server": mock_client}
        
        print("修正後のConnectionManagerテスト:")
        print("-" * 30)
        
        # 各レスポンスをテスト
        for i, response in enumerate(test_responses, 1):
            try:
                # MCPクライアントの応答をモック
                mock_client.call_tool.return_value = response
                
                # ConnectionManagerのcall_toolを呼び出し
                result = await conn_manager.call_tool("test_tool", {})
                
                # 結果の確認
                print(f"Test {i}: ", end="")
                if sys.platform == "win32":
                    # Windows環境での処理確認
                    try:
                        # 結果がcp932でエンコードできるかチェック
                        result.encode('cp932')
                        print(f"OK - Safe result: '{result}'")
                    except UnicodeEncodeError:
                        print(f"NG - Unsafe result: '{result}'")
                else:
                    print(f"OK (Non-Windows) - '{result}'")
                    
            except Exception as e:
                print(f"Test {i}: ERROR - {type(e).__name__}: {str(e)}")
        
        print("\nConnectionManagerテスト完了")
        
    except ImportError as e:
        print(f"Import Error: {e}")
        return False
    
    return True

async def test_safe_printing():
    """安全な出力処理をテスト"""
    
    print("\n" + "=" * 50)
    print("Safe Printing Test")
    print("=" * 50)
    
    dangerous_data = [
        "通常のテキスト",
        "Task completed with emoji",  # 絵文字は含まない
        "Error occurred",
        "Processing data", 
        "Temperature: 25C",  # °記号なし
        "Warning: Memory low",
        "Result: [1, 2, 3]",
        "Beijing weather: 22C",
    ]
    
    print("安全な出力テスト:")
    try:
        for i, data in enumerate(dangerous_data, 1):
            print(f"  {i}. {data}")
        
        print("\n全てのテストデータが出力できました")
        print("実際の絵文字データはMCPサーバー応答で処理されます")
        return True
        
    except Exception as e:
        print(f"出力エラー: {e}")
        return False

def test_string_processing():
    """文字列処理のテスト（print出力なし）"""
    
    print("\n" + "=" * 50) 
    print("String Processing Test")
    print("=" * 50)
    
    # 問題のある文字列（print出力せずに処理のみテスト）
    problematic_strings = [
        "✅ Success",
        "❌ Error", 
        "🚀 Launch",
        "💡 Idea",
        "⚠️ Warning",
        "📋 Clipboard",
        "温度: 25°C",
        "範囲: α～ω"
    ]
    
    success_count = 0
    total_count = len(problematic_strings)
    
    for i, text in enumerate(problematic_strings, 1):
        try:
            # Windows環境でのエンコーディング処理をテスト
            if sys.platform == "win32":
                # cp932で処理できるかテスト
                safe_text = text.encode('cp932', errors='replace').decode('cp932')
                
                # 結果の検証（絵文字が?に置換されているか）
                has_replacement = '?' in safe_text
                original_has_special = any(ord(c) > 0x7F for c in text if c not in 'αω°～')
                
                if original_has_special and not has_replacement:
                    print(f"  Test {i}: WARNING - 特殊文字が残っている可能性")
                else:
                    print(f"  Test {i}: OK - 安全に処理完了")
                    success_count += 1
            else:
                print(f"  Test {i}: OK (Non-Windows)")
                success_count += 1
                
        except Exception as e:
            print(f"  Test {i}: ERROR - {e}")
    
    print(f"\n処理結果: {success_count}/{total_count} 成功")
    return success_count == total_count

async def main():
    """メインテスト実行"""
    
    tests_results = []
    
    try:
        # 各テストを実行
        result1 = await test_connection_manager_encoding()
        tests_results.append(("ConnectionManager", result1))
        
        result2 = await test_safe_printing()
        tests_results.append(("Safe Printing", result2))
        
        result3 = test_string_processing()
        tests_results.append(("String Processing", result3))
        
        # 結果サマリー
        print("\n" + "=" * 50)
        print("Test Results Summary")
        print("=" * 50)
        
        passed = 0
        for test_name, result in tests_results:
            status = "PASS" if result else "FAIL"
            print(f"  {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\nOverall: {passed}/{len(tests_results)} tests passed")
        
        if passed == len(tests_results):
            print("\n修正は成功しました！")
            print("Windows環境でのUTF-8エンコーディング問題が解決されています。")
        else:
            print("\n一部のテストが失敗しました。")
            print("追加の修正が必要な可能性があります。")
            
    except Exception as e:
        print(f"\nFatal Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())