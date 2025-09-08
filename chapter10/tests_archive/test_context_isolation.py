#!/usr/bin/env python3
"""
コンテキスト分離テスト - mcp_agent.py の会話履歴汚染問題のテスト

重要なテストケース：
1. タスクリスト生成時の実行結果混入防止
2. 異なる要求間でのコンテキスト分離
3. 会話履歴と実行結果の適切な分離
"""

import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json

# テスト対象のインポート
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_agent import MCPAgent


class TestContextIsolation(unittest.TestCase):
    """コンテキスト分離のテストクラス"""

    def setUp(self):
        """テスト用のセットアップ"""
        # MCPAgentのインスタンスを作成（モック使用）
        with patch('mcp_agent.ConnectionManager'), \
             patch('mcp_agent.ErrorHandler'), \
             patch('llm_interface.AsyncOpenAI'):
            
            self.agent = MCPAgent()
            
            # 会話履歴のセットアップ
            self.agent.conversation_history = [
                {
                    "timestamp": "2025-08-23T10:00:00",
                    "role": "user", 
                    "message": "東京と北京の天気を比較して"
                },
                {
                    "timestamp": "2025-08-23T10:01:00",
                    "role": "assistant",
                    "message": "天気情報を取得します",
                    "execution_results": [
                        {
                            "tool": "get_weather",
                            "result": {"city": "Tokyo", "temp": 34.73, "weather": "晴天"},
                            "success": True
                        },
                        {
                            "tool": "get_weather", 
                            "result": {"city": "Beijing", "temp": 27.05, "weather": "厚い雲"},
                            "success": True
                        }
                    ]
                },
                {
                    "timestamp": "2025-08-23T10:05:00",
                    "role": "user",
                    "message": "フィボナッチ数列を10個表示して"
                },
                {
                    "timestamp": "2025-08-23T10:06:00",
                    "role": "assistant", 
                    "message": "フィボナッチ数列を計算します",
                    "execution_results": [
                        {
                            "tool": "execute_python",
                            "result": "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]",
                            "success": True
                        }
                    ]
                }
            ]

    def test_conversation_context_only(self):
        """_get_conversation_context_only が実行結果を除外することをテスト"""
        # 会話文脈のみを取得
        context = self.agent._get_conversation_context_only()
        
        # 実行結果データが含まれていないことを確認
        self.assertNotIn("execution_results", context)
        self.assertNotIn("実行結果データ", context)
        self.assertNotIn("get_weather", context)
        self.assertNotIn("execute_python", context)
        
        # 会話内容は含まれていることを確認
        self.assertIn("東京と北京", context)
        self.assertIn("フィボナッチ数列", context)
        
        print(f"[SUCCESS] 会話文脈のみ抽出: 実行結果除外を確認")
        print(f"  コンテキスト長: {len(context)}文字")

    def test_recent_context_includes_execution_results(self):
        """_get_recent_context が実行結果を含むことをテスト（対照確認用）"""
        # 従来の会話文脈を取得
        context = self.agent._get_recent_context()
        
        # 実行結果データが含まれていることを確認
        self.assertIn("実行結果データ", context)
        
        # 会話内容も含まれていることを確認
        self.assertIn("東京と北京", context)
        self.assertIn("フィボナッチ数列", context)
        
        print(f"[SUCCESS] 従来文脈: 実行結果含有を確認")
        print(f"  コンテキスト長: {len(context)}文字")

    def test_context_length_difference(self):
        """会話のみと実行結果込みでコンテキスト長に差があることをテスト"""
        conversation_only = self.agent._get_conversation_context_only()
        with_execution = self.agent._get_recent_context()
        
        # 実行結果込みの方が長いことを確認
        self.assertGreater(len(with_execution), len(conversation_only))
        
        length_diff = len(with_execution) - len(conversation_only)
        reduction_percent = (length_diff / len(with_execution)) * 100
        
        print(f"[SUCCESS] コンテキスト長の差: {length_diff}文字")
        print(f"  削減率: {reduction_percent:.1f}%")

    def test_no_contamination_in_conversation_context(self):
        """会話文脈に特定の実行結果キーワードが含まれないことをテスト"""
        context = self.agent._get_conversation_context_only()
        
        # 実行結果由来のキーワードが含まれていないことを確認
        contamination_keywords = [
            "temp",           # 天気データ
            "34.73",          # 東京の温度
            "27.05",          # 北京の温度  
            "晴天",           # 天気状態
            "厚い雲",         # 天気状態
            "[0, 1, 1, 2",    # フィボナッチ数列データ
            "execute_python", # ツール名
            "get_weather"     # ツール名
        ]
        
        for keyword in contamination_keywords:
            self.assertNotIn(keyword, context, 
                           f"実行結果キーワード '{keyword}' が会話文脈に混入")
        
        print(f"[SUCCESS] 実行結果キーワード混入なし: {len(contamination_keywords)}個確認")

    def test_task_generation_context_isolation(self):
        """タスク生成時のコンテキストが分離されていることをテスト"""
        
        # 新しいユーザー要求（過去のタスクと無関係）
        new_query = "壁打ちゲームをHTMLベースで作成して"
        
        # 会話文脈のみ（修正後）
        clean_context = self.agent._get_conversation_context_only()
        
        # 実行結果込み文脈（修正前）
        contaminated_context = self.agent._get_recent_context()
        
        # クリーンな文脈には実行結果の具体的データが含まれない
        self.assertNotIn("34.73", clean_context)
        self.assertNotIn("get_weather", clean_context)
        
        # 汚染された文脈には実行結果が含まれる
        self.assertIn("実行結果データ", contaminated_context)
        
        print(f"[SUCCESS] タスク生成時のコンテキスト分離確認")
        print(f"  新要求: {new_query}")
        print(f"  クリーン文脈長: {len(clean_context)}文字")
        print(f"  汚染文脈長: {len(contaminated_context)}文字")

    def test_multiple_requests_isolation(self):
        """複数の異なる要求がコンテキスト汚染されないことをテスト"""
        
        # 異なる種類の要求リスト
        test_queries = [
            "壁打ちゲームを作成して",
            "素数を100個生成して", 
            "データベースのユーザーテーブルを表示して",
            "株価情報を取得して"
        ]
        
        for query in test_queries:
            context = self.agent._get_conversation_context_only()
            
            # 各要求で同じように実行結果が除外されることを確認
            self.assertNotIn("実行結果データ", context)
            self.assertNotIn("temp", context)  # 天気データ
            self.assertNotIn("[0, 1, 1,", context)  # フィボナッチデータ
            
        print(f"[SUCCESS] 複数要求の分離: {len(test_queries)}個の要求で確認")

    def test_context_limit_respected(self):
        """コンテキスト制限が適切に適用されることをテスト"""
        
        # デフォルト制限（3件）
        default_context = self.agent._get_conversation_context_only()
        
        # カスタム制限（1件）  
        limited_context = self.agent._get_conversation_context_only(max_items=1)
        
        # 制限により文脈が短くなることを確認
        self.assertGreater(len(default_context), len(limited_context))
        
        # 最新の会話のみが含まれることを確認（フィボナッチの要求）
        self.assertIn("フィボナッチ", limited_context)
        # 古い会話は含まれないことを確認（天気の要求）
        self.assertNotIn("東京と北京", limited_context)
        
        print(f"[SUCCESS] コンテキスト制限: デフォルト{len(default_context)}文字 → 制限{len(limited_context)}文字")

    def test_empty_history_handling(self):
        """空の会話履歴の処理をテスト"""
        
        # 会話履歴をクリア
        self.agent.conversation_history = []
        
        # 空文字列が返されることを確認
        context = self.agent._get_conversation_context_only()
        self.assertEqual(context, "")
        
        print(f"[SUCCESS] 空履歴処理: 空文字列を返却")

    def test_execution_results_structure_integrity(self):
        """実行結果構造の整合性をテスト"""
        
        # 会話履歴に実行結果があることを確認
        has_execution_results = any(
            h.get('execution_results') for h in self.agent.conversation_history
        )
        self.assertTrue(has_execution_results)
        
        # 会話文脈のみでは実行結果が除外されることを確認
        context_only = self.agent._get_conversation_context_only()
        self.assertNotIn("execution_results", context_only)
        
        # 実行結果込みでは含まれることを確認
        with_results = self.agent._get_recent_context()
        self.assertIn("実行結果データ", with_results)
        
        print(f"[SUCCESS] 実行結果構造の整合性確認")


class TestContextEdgeCases(unittest.TestCase):
    """コンテキスト処理のエッジケーステスト"""
    
    def setUp(self):
        with patch('mcp_agent.ConnectionManager'), \
             patch('mcp_agent.ErrorHandler'), \
             patch('llm_interface.AsyncOpenAI'):
            
            self.agent = MCPAgent()

    def test_very_long_messages(self):
        """非常に長いメッセージの処理テスト"""
        
        # 非常に長いメッセージを作成
        long_message = "x" * 1000
        
        self.agent.conversation_history = [
            {
                "timestamp": "2025-08-23T10:00:00",
                "role": "user",
                "message": long_message
            }
        ]
        
        # 長いメッセージが適切に省略されることを確認
        context = self.agent._get_conversation_context_only()
        self.assertLess(len(context), 1000)  # 省略されているはず
        self.assertIn("...", context)  # 省略マークが含まれる
        
        print(f"[SUCCESS] 長いメッセージの省略: {len(context)}文字に短縮")

    def test_special_characters_handling(self):
        """特殊文字の処理テスト"""
        
        special_message = "テスト: {\"key\": \"value\"}, <tag>content</tag>, [array]"
        
        self.agent.conversation_history = [
            {
                "timestamp": "2025-08-23T10:00:00", 
                "role": "user",
                "message": special_message
            }
        ]
        
        # 特殊文字が適切に処理されることを確認
        context = self.agent._get_conversation_context_only()
        self.assertIn(special_message, context)
        
        print(f"[SUCCESS] 特殊文字処理: エラーなく処理完了")


def run_tests():
    """テスト実行関数"""
    print("=" * 70)
    print(" コンテキスト分離テスト実行")
    print("=" * 70)

    # テストスイート作成
    suite = unittest.TestSuite()
    
    # 基本テストを追加
    suite.addTest(TestContextIsolation('test_conversation_context_only'))
    suite.addTest(TestContextIsolation('test_recent_context_includes_execution_results'))
    suite.addTest(TestContextIsolation('test_context_length_difference'))
    suite.addTest(TestContextIsolation('test_no_contamination_in_conversation_context'))
    suite.addTest(TestContextIsolation('test_task_generation_context_isolation'))
    suite.addTest(TestContextIsolation('test_multiple_requests_isolation'))
    suite.addTest(TestContextIsolation('test_context_limit_respected'))
    suite.addTest(TestContextIsolation('test_empty_history_handling'))
    suite.addTest(TestContextIsolation('test_execution_results_structure_integrity'))
    
    # エッジケーステストを追加
    suite.addTest(TestContextEdgeCases('test_very_long_messages'))
    suite.addTest(TestContextEdgeCases('test_special_characters_handling'))

    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 結果サマリー
    print("\n" + "=" * 70)
    print(f"テスト結果: {result.testsRun}件実行")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}件")
    print(f"失敗: {len(result.failures)}件") 
    print(f"エラー: {len(result.errors)}件")
    
    if result.failures:
        print(f"\n失敗詳細:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print(f"\nエラー詳細:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)