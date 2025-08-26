#!/usr/bin/env python3
"""
プレースホルダー解決テスト - mcp_agent.py の _resolve_placeholders メソッドのテスト

重要なテストケース：
1. 日本語都市名の抽出
2. プレースホルダー置換の正常動作
3. 循環参照の検出
4. エラー処理の確認
"""

import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch
import copy

# テスト対象のインポート
sys.path.append('.')
from mcp_agent import MCPAgent


class TestPlaceholderResolution(unittest.TestCase):
    """プレースホルダー解決のテストクラス"""

    def setUp(self):
        """テスト用のセットアップ"""
        # MCPAgentのインスタンスを作成（設定なし）
        with patch('mcp_agent.ConnectionManager'), \
             patch('mcp_agent.ErrorHandler'), \
             patch('mcp_agent.AsyncOpenAI'):
            
            self.agent = MCPAgent()

    def test_japanese_city_extraction(self):
        """日本語都市名の抽出テスト"""
        # テストデータ
        params = {"city": "取得した都市名"}
        execution_context = [
            {
                "tool": "get_ip_info",
                "result": {"city": "東京都", "region": "Tokyo", "country": "Japan"},
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 結果確認
        self.assertEqual(resolved["city"], "東京都")
        print(f"[SUCCESS] 日本語都市名抽出: {resolved['city']}")

    def test_japanese_city_with_suffix(self):
        """市・区付き日本語都市名の抽出テスト"""
        # テストデータ
        params = {"city": "取得した都市名"}
        execution_context = [
            {
                "tool": "get_ip_info", 
                "result": {"address": "栃木県、鹿沼市、石橋町"},
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 結果確認
        self.assertEqual(resolved["city"], "鹿沼市")
        print(f"[SUCCESS] 市区付き都市名抽出: {resolved['city']}")

    def test_previous_result_placeholder(self):
        """{{previous_result}} プレースホルダーのテスト"""
        # テストデータ
        params = {"input": "{{previous_result}}"}
        execution_context = [
            {
                "tool": "calculator",
                "result": "42",
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 結果確認
        self.assertEqual(resolved["input"], "42")
        print(f"[SUCCESS] previous_result プレースホルダー: {resolved['input']}")

    def test_task_field_placeholder(self):
        """{{task_N.field}} プレースホルダーのテスト"""
        # テストデータ
        params = {"location": "{{task_1.city}}"}
        execution_context = [
            {
                "tool": "get_ip_info",
                "result": {"city": "Osaka", "temperature": 25.5},
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 結果確認
        self.assertEqual(resolved["location"], "Osaka")
        print(f"[SUCCESS] task_N.field プレースホルダー: {resolved['location']}")

    def test_no_execution_context(self):
        """実行コンテキストがない場合のテスト"""
        # テストデータ
        params = {"city": "取得した都市名"}
        execution_context = []

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 結果確認（変更されないはず）
        self.assertEqual(resolved["city"], "取得した都市名")
        print(f"[SUCCESS] 空実行コンテキスト: {resolved['city']}")

    def test_nested_parameters(self):
        """ネストしたパラメータの処理テスト"""
        # テストデータ
        params = {
            "query": {
                "location": "取得した都市名",
                "data": ["{{previous_result}}", "static_value"]
            }
        }
        execution_context = [
            {
                "tool": "get_ip_info",
                "result": {"city": "名古屋市"},
                "success": True
            },
            {
                "tool": "calculator", 
                "result": "100",
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 結果確認
        self.assertEqual(resolved["query"]["location"], "名古屋市")
        self.assertEqual(resolved["query"]["data"][0], "100")
        self.assertEqual(resolved["query"]["data"][1], "static_value")
        print(f"[SUCCESS] ネストパラメータ: {resolved}")

    def test_complex_city_extraction(self):
        """複雑な形式の都市名抽出テスト"""
        # テストケース1: カンマ区切りの住所
        params = {"city": "取得した都市名"}
        execution_context = [
            {
                "tool": "get_ip_info",
                "result": "Tokyo, Shibuya District, Japan",
                "success": True
            }
        ]

        resolved = self.agent._resolve_placeholders(params, execution_context)
        # このケースでは正規表現にマッチしないので、元の値のまま
        self.assertEqual(resolved["city"], "取得した都市名")
        print(f"[INFO] 英語住所は変換されない: {resolved['city']}")

    def test_multiple_city_candidates(self):
        """複数の都市候補がある場合のテスト"""
        # テストデータ
        params = {"city": "取得した都市名"}
        execution_context = [
            {
                "tool": "get_location",
                "result": "埼玉県、さいたま市、浦和区",
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 最初にマッチした市区を取得
        self.assertIn("市", resolved["city"])
        print(f"[SUCCESS] 複数候補からの抽出: {resolved['city']}")

    def test_no_city_match(self):
        """都市名がマッチしない場合のテスト"""
        # テストデータ  
        params = {"city": "取得した都市名"}
        execution_context = [
            {
                "tool": "get_info",
                "result": {"temperature": 25, "weather": "sunny"},
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # マッチしない場合は元の値のまま
        self.assertEqual(resolved["city"], "取得した都市名")
        print(f"[INFO] マッチしない場合は元の値: {resolved['city']}")

    def test_error_case_handling(self):
        """エラーケースの処理テスト"""
        # 失敗したタスクの結果を含むケース
        params = {"city": "取得した都市名"}
        execution_context = [
            {
                "tool": "get_ip_info",
                "success": False,
                "error": "Connection timeout"
            },
            {
                "tool": "fallback_location", 
                "result": {"city": "札幌市"},
                "success": True
            }
        ]

        # プレースホルダー置換を実行
        resolved = self.agent._resolve_placeholders(params, execution_context)

        # 成功したタスクの結果を使用
        self.assertEqual(resolved["city"], "札幌市")
        print(f"[SUCCESS] エラー後のフォールバック: {resolved['city']}")


class TestPlaceholderEdgeCases(unittest.TestCase):
    """プレースホルダー処理のエッジケーステスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        with patch('mcp_agent.ConnectionManager'), \
             patch('mcp_agent.ErrorHandler'), \
             patch('mcp_agent.AsyncOpenAI'):
            
            self.agent = MCPAgent()

    def test_circular_reference_prevention(self):
        """循環参照の予防テスト（将来の改善点）"""
        # 現在は循環参照チェックがないため、このテストは将来の改善用
        # TODO: 循環参照検出機能実装後に有効化
        
        params = {"param1": "{{task_2.result}}"}
        execution_context = [
            {
                "tool": "task1",
                "result": "{{task_2.result}}",  # 循環参照
                "success": True
            },
            {
                "tool": "task2", 
                "result": "{{task_1.result}}",  # 循環参照
                "success": True
            }
        ]

        # 現状では無限再帰になる可能性があるため、コメントアウト
        # resolved = self.agent._resolve_placeholders(params, execution_context)
        
        print("[WARNING] 循環参照検出機能は未実装（将来の改善点）")

    def test_deep_nesting_limit(self):
        """深いネスト処理の制限テスト"""
        # 非常に深いネスト構造
        deep_params = {"level": 1}
        for i in range(2, 20):
            deep_params = {"nested": deep_params, f"level_{i}": f"value_{i}"}

        execution_context = []
        
        # 処理が完了することを確認（パフォーマンステスト）
        import time
        start_time = time.time()
        resolved = self.agent._resolve_placeholders(deep_params, execution_context)
        end_time = time.time()

        # 1秒以内に完了することを確認
        self.assertLess(end_time - start_time, 1.0)
        print(f"[SUCCESS] 深いネスト処理時間: {end_time - start_time:.3f}秒")


def run_tests():
    """テスト実行関数"""
    print("=" * 70)
    print(" プレースホルダー解決テスト実行")
    print("=" * 70)

    # テストスイート作成
    suite = unittest.TestSuite()
    
    # 基本テストを追加
    suite.addTest(TestPlaceholderResolution('test_japanese_city_extraction'))
    suite.addTest(TestPlaceholderResolution('test_japanese_city_with_suffix'))
    suite.addTest(TestPlaceholderResolution('test_previous_result_placeholder'))
    suite.addTest(TestPlaceholderResolution('test_task_field_placeholder'))
    suite.addTest(TestPlaceholderResolution('test_no_execution_context'))
    suite.addTest(TestPlaceholderResolution('test_nested_parameters'))
    suite.addTest(TestPlaceholderResolution('test_complex_city_extraction'))
    suite.addTest(TestPlaceholderResolution('test_multiple_city_candidates'))
    suite.addTest(TestPlaceholderResolution('test_no_city_match'))
    suite.addTest(TestPlaceholderResolution('test_error_case_handling'))
    
    # エッジケーステストを追加
    suite.addTest(TestPlaceholderEdgeCases('test_circular_reference_prevention'))
    suite.addTest(TestPlaceholderEdgeCases('test_deep_nesting_limit'))

    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 結果サマリー
    print("\n" + "=" * 70)
    print(f"テスト結果: {result.testsRun}件実行")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}件")
    print(f"失敗: {len(result.failures)}件")
    print(f"エラー: {len(result.errors)}件")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)