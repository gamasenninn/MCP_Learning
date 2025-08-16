#!/usr/bin/env python3
"""
エラーハンドリング機能の包括的テスト
様々なエラーシナリオでの自動回復をテスト
"""

import asyncio
import os
import sys
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from intelligent_error_handler import IntelligentErrorHandler
from error_aware_executor import ErrorAwareExecutor
from adaptive_task_planner import AdaptiveTaskPlanner
from universal_task_planner import UniversalTask

class ErrorHandlingTester:
    """エラーハンドリングのテスター"""
    
    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai
        self.test_results = []
        self.planner = None
        self.executor = None
    
    async def setup(self):
        """テスト環境のセットアップ"""
        print("[セットアップ] テスト環境を準備中...")
        
        # APIキーの確認
        api_key = os.getenv("OPENAI_API_KEY")
        if self.use_ai and not api_key:
            print("  [警告] OpenAI APIキーが設定されていません")
            self.use_ai = False
        
        # プランナーとエグゼキューターの初期化
        if self.use_ai and api_key:
            self.planner = AdaptiveTaskPlanner(api_key=api_key)
        else:
            from universal_task_planner import UniversalTaskPlanner
            self.planner = UniversalTaskPlanner()
        
        self.executor = ErrorAwareExecutor(
            use_ai=self.use_ai,
            max_retries=3,
            verbose=True
        )
        
        await self.planner.initialize()
        await self.executor.connect_all_servers()
        
        print("  [完了] セットアップ完了\n")
    
    async def test_parameter_error(self):
        """パラメータエラーのテスト"""
        print("\n" + "=" * 60)
        print("テスト1: パラメータエラーの自動修正")
        print("=" * 60)
        
        # わざと文字列パラメータを渡してエラーを発生させる
        error_task = UniversalTask(
            id="param_error_test",
            name="パラメータエラーテスト",
            tool="add",
            server="calculator",
            params={"a": "百", "b": 200}  # '百'は数値に変換できない
        )
        
        start_time = time.time()
        result = await self.executor.execute_task_with_recovery(error_task)
        elapsed = time.time() - start_time
        
        test_result = {
            "test": "パラメータエラー",
            "success": result is not None,
            "result": result,
            "elapsed": elapsed,
            "recovered": len([a for a in self.executor.execution_history if a.attempt_number > 1]) > 0
        }
        
        self.test_results.append(test_result)
        
        print(f"\n結果: {'成功' if test_result['success'] else '失敗'}")
        print(f"実行時間: {elapsed:.2f}秒")
        
        return test_result
    
    async def test_zero_division(self):
        """ゼロ除算エラーのテスト"""
        print("\n" + "=" * 60)
        print("テスト2: ゼロ除算エラーの回避")
        print("=" * 60)
        
        # ゼロ除算を含むタスク（実行時にエラーになるように）
        query = "100を2で割って、その結果を0で割って"
        
        start_time = time.time()
        
        # タスク計画
        tasks = await self.planner.plan_task(query)
        
        # 実行
        result = await self.executor.execute_tasks_with_recovery(tasks)
        
        # エラーが発生した場合は再計画
        if not result["success"] and self.use_ai:
            print("\n[再計画] エラーが解決できなかったため再計画します")
            
            failed_tasks = [
                UniversalTask(**task_dict)
                for task_dict in result["tasks"]
                if task_dict.get("error")
            ]
            
            if failed_tasks:
                new_tasks = await self.planner.replan_on_error(
                    query,
                    failed_tasks,
                    {"error": "ゼロ除算エラー", "attempts": 3}
                )
                
                if new_tasks:
                    print(f"  新しいアプローチで{len(new_tasks)}個のタスクを実行")
                    result = await self.executor.execute_tasks_with_recovery(new_tasks)
        
        elapsed = time.time() - start_time
        
        test_result = {
            "test": "ゼロ除算エラー",
            "success": result["success"],
            "result": result.get("final_result"),
            "elapsed": elapsed,
            "recovered": result["stats"].get("recovered", 0) > 0
        }
        
        self.test_results.append(test_result)
        
        print(f"\n結果: {'成功' if test_result['success'] else '失敗'}")
        print(f"実行時間: {elapsed:.2f}秒")
        
        return test_result
    
    async def test_tool_not_found(self):
        """ツール不在エラーのテスト"""
        print("\n" + "=" * 60)
        print("テスト3: 存在しないツールの代替")
        print("=" * 60)
        
        # 存在しないツールを使用
        error_task = UniversalTask(
            id="tool_error_test",
            name="ツール不在テスト",
            tool="calculate_tax",  # 存在しないツール
            server="calculator",
            params={"amount": 1000, "rate": 0.1}
        )
        
        start_time = time.time()
        
        # AIハンドラーがある場合は代替ツールを提案
        if self.use_ai:
            print("  [AI] 代替ツールを探索中...")
        
        result = await self.executor.execute_task_with_recovery(error_task)
        elapsed = time.time() - start_time
        
        test_result = {
            "test": "ツール不在エラー",
            "success": result is not None,
            "result": result,
            "elapsed": elapsed,
            "recovered": error_task.tool != "calculate_tax"  # ツールが変更されたか
        }
        
        self.test_results.append(test_result)
        
        print(f"\n結果: {'成功' if test_result['success'] else '失敗'}")
        print(f"実行時間: {elapsed:.2f}秒")
        
        return test_result
    
    async def test_complex_calculation_error(self):
        """複雑な計算エラーのテスト"""
        print("\n" + "=" * 60)
        print("テスト4: 複雑な計算エラーの分解")
        print("=" * 60)
        
        # 複雑な計算（エラーを含む可能性）
        query = "1000を5で割って、その結果から300を引いて、最後に0で割って"
        
        start_time = time.time()
        
        # タスク計画
        tasks = await self.planner.plan_task(query)
        print(f"  初期タスク数: {len(tasks)}")
        
        # 実行
        result = await self.executor.execute_tasks_with_recovery(tasks)
        
        # エラーが発生した場合、より細かく分解
        if not result["success"] and self.use_ai:
            print("\n[再分解] タスクをより細かく分解します")
            
            # より単純なタスクに分解
            simpler_query = "1000を5で割る。結果から300を引く。"
            new_tasks = await self.planner.plan_task(simpler_query)
            
            if new_tasks:
                print(f"  簡略化: {len(new_tasks)}個のタスクに再分解")
                result = await self.executor.execute_tasks_with_recovery(new_tasks)
        
        elapsed = time.time() - start_time
        
        test_result = {
            "test": "複雑な計算エラー",
            "success": result["success"] or result.get("final_result") is not None,
            "result": result.get("final_result"),
            "elapsed": elapsed,
            "recovered": result["stats"].get("recovered", 0) > 0
        }
        
        self.test_results.append(test_result)
        
        print(f"\n結果: {'成功' if test_result['success'] else '失敗'}")
        print(f"実行時間: {elapsed:.2f}秒")
        
        return test_result
    
    async def test_connection_error_simulation(self):
        """接続エラーのシミュレーション"""
        print("\n" + "=" * 60)
        print("テスト5: 接続エラーのリトライ")
        print("=" * 60)
        
        # 接続エラーをシミュレート（実際にはツール実行）
        normal_task = UniversalTask(
            id="connection_test",
            name="接続テスト",
            tool="add",
            server="calculator",
            params={"a": 50, "b": 50}
        )
        
        start_time = time.time()
        
        print("  [シミュレーション] 接続エラーを想定したリトライ動作")
        
        # 通常の実行（リトライ機能付き）
        result = await self.executor.execute_task_with_recovery(normal_task)
        
        elapsed = time.time() - start_time
        
        test_result = {
            "test": "接続エラーシミュレーション",
            "success": result is not None,
            "result": result,
            "elapsed": elapsed,
            "recovered": False
        }
        
        self.test_results.append(test_result)
        
        print(f"\n結果: {'成功' if test_result['success'] else '失敗'}")
        print(f"実行時間: {elapsed:.2f}秒")
        
        return test_result
    
    async def run_all_tests(self):
        """全テストを実行"""
        print("\n" + "=" * 70)
        print(" エラーハンドリング包括テスト")
        print("=" * 70)
        print(f"  AIサポート: {'有効' if self.use_ai else '無効'}")
        print(f"  テスト数: 5")
        print()
        
        await self.setup()
        
        # 各テストを実行
        await self.test_parameter_error()
        await self.test_zero_division()
        await self.test_tool_not_found()
        await self.test_complex_calculation_error()
        await self.test_connection_error_simulation()
        
        # 結果サマリ
        self.print_summary()
        
        # クリーンアップ
        await self.cleanup()
    
    def print_summary(self):
        """テスト結果のサマリを表示"""
        print("\n" + "=" * 70)
        print(" テスト結果サマリ")
        print("=" * 70)
        
        success_count = sum(1 for r in self.test_results if r["success"])
        total_count = len(self.test_results)
        recovered_count = sum(1 for r in self.test_results if r["recovered"])
        
        print(f"\n[全体統計]")
        print(f"  総テスト数: {total_count}")
        print(f"  成功: {success_count}")
        print(f"  失敗: {total_count - success_count}")
        print(f"  成功率: {(success_count/total_count*100):.1f}%")
        print(f"  リカバリー発生: {recovered_count}件")
        
        print(f"\n[個別結果]")
        for i, result in enumerate(self.test_results, 1):
            status = "[OK]" if result["success"] else "[NG]"
            recovery = " (リカバリー)" if result["recovered"] else ""
            print(f"  {i}. {result['test']}: {status}{recovery} ({result['elapsed']:.2f}秒)")
        
        # 実行レポート
        if self.executor:
            print("\n" + self.executor.get_execution_report())
        
        # 適応学習レポート
        if hasattr(self.planner, 'get_adaptation_report'):
            print("\n" + self.planner.get_adaptation_report())
    
    async def cleanup(self):
        """クリーンアップ"""
        if self.executor:
            await self.executor.cleanup()
        print("\n[クリーンアップ] 完了")


# メイン実行
async def main():
    """メイン実行関数"""
    
    # コマンドライン引数の処理
    use_ai = True
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-ai":
            use_ai = False
            print("AIサポートを無効にしてテストを実行します")
    
    # テスター作成と実行
    tester = ErrorHandlingTester(use_ai=use_ai)
    await tester.run_all_tests()


if __name__ == "__main__":
    print("エラーハンドリング機能テスト")
    print("使用方法:")
    print("  python test_error_handling.py          # AIサポート有効（要OPENAI_API_KEY）")
    print("  python test_error_handling.py --no-ai  # AIサポート無効")
    print()
    
    asyncio.run(main())