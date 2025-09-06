#!/usr/bin/env python3
"""
LLM SQL correction simple integration test
LLMによるSQL自動修正機能のシンプルな統合テスト
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from task_executor import TaskExecutor
from error_handler import ErrorHandler
from config_manager import Config, LLMConfig, ExecutionConfig, ErrorHandlingConfig


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_judgment_always_executed_simple():
    """
    LLM判断が常時実行されることの簡単なテスト
    成功・失敗に関わらず、すべての結果でLLM判断が実行されることを確認
    """
    # モック設定
    mock_config = Config(
        llm=LLMConfig(model="gpt-4o-mini"),
        execution=ExecutionConfig(max_retries=1),
        error_handling=ErrorHandlingConfig(auto_correct_params=True)
    )
    
    mock_llm = AsyncMock()
    mock_connection_manager = MagicMock()
    
    # ツール実行は成功するが、結果が空の場合をシミュレート
    mock_connection_manager.call_tool = AsyncMock(return_value="")  # 空の結果
    
    # LLMInterfaceをモックしてErrorHandlerを初期化
    mock_llm_interface = Mock()
    error_handler = ErrorHandler(config=mock_config, llm_interface=mock_llm_interface, verbose=True)
    
    task_executor = TaskExecutor(
        task_manager=MagicMock(),
        connection_manager=mock_connection_manager,
        state_manager=MagicMock(),
        display_manager=MagicMock(),
        llm_interface=mock_llm_interface,
        config=mock_config,
        error_handler=error_handler,
        verbose=True
    )
    
    # LLMInterfaceのjudge_tool_execution_resultメソッドをモック
    mock_llm_interface.judge_tool_execution_result = AsyncMock(return_value={
        "is_success": False,
        "needs_retry": True,
        "error_reason": "空の結果が返されました",
        "corrected_params": {
            "sql": "SELECT p.name, SUM(s.total_amount) FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.name"
        },
        "processed_result": "修正されたクエリで再実行が必要です",
        "summary": "SQLクエリを修正しました"
    })
    
    # ツール実行（空の結果でもLLM判断が実行されることをテスト）
    result = await task_executor.execute_tool_with_retry(
        tool="execute_safe_query",
        params={"sql": "SELECT 商品名 FROM 売上テーブル"},
        description="商品名取得テスト"
    )
    
    # 検証
    assert mock_connection_manager.call_tool.call_count >= 1  # ツールが実行された
    assert mock_llm_interface.judge_tool_execution_result.call_count >= 1   # LLM判断が実行された
    assert result is not None
    print("✅ LLM判断常時実行テスト成功")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_sql_parameter_correction():
    """
    LLMによるSQL パラメータ修正テスト
    不正なSQLパラメータがLLMによって修正されることを確認
    """
    mock_config = Config(
        llm=LLMConfig(model="gpt-4o-mini"),
        execution=ExecutionConfig(max_retries=2),
        error_handling=ErrorHandlingConfig(auto_correct_params=True)
    )
    
    mock_llm = AsyncMock()
    mock_connection_manager = MagicMock()
    
    # 1回目は空、2回目は成功結果を返す
    call_results = ["", '{"results": [{"name": "iPhone", "sales": 1000000}]}']
    mock_connection_manager.call_tool = AsyncMock(side_effect=call_results)
    
    # LLMInterfaceをモックしてErrorHandlerを初期化
    mock_llm_interface = Mock()
    error_handler = ErrorHandler(config=mock_config, llm_interface=mock_llm_interface, verbose=True)
    
    task_executor = TaskExecutor(
        task_manager=MagicMock(),
        connection_manager=mock_connection_manager,
        state_manager=MagicMock(),
        display_manager=MagicMock(),
        llm_interface=mock_llm_interface,
        config=mock_config,
        error_handler=error_handler,
        verbose=True
    )
    
    # 1回目: 失敗と判断してリトライ
    # 2回目: 成功と判断
    llm_responses = [
        {
            "is_success": False,
            "needs_retry": True,
            "error_reason": "日本語のテーブル名が使用されています",
            "corrected_params": {
                "sql": "SELECT p.name AS product_name, SUM(s.total_amount) AS total_sales FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.name"
            },
            "processed_result": "SQLを修正してリトライします",
            "summary": "適切なJOINクエリに修正"
        },
        {
            "is_success": True,
            "needs_retry": False,
            "processed_result": "商品の売上データが正常に取得されました",
            "summary": "クエリが成功しました"
        }
    ]
    
    # LLMInterfaceのjudge_tool_execution_resultメソッドをモック（段階的レスポンス）
    mock_llm_interface.judge_tool_execution_result = AsyncMock(side_effect=llm_responses)
    
    # テスト実行
    result = await task_executor.execute_tool_with_retry(
        tool="execute_safe_query",
        params={"sql": "SELECT 商品名, SUM(売上) FROM 売上テーブル GROUP BY 商品名"},
        description="商品別売上合計取得"
    )
    
    # 検証
    assert mock_connection_manager.call_tool.call_count == 2  # リトライで2回実行
    assert mock_llm_interface.judge_tool_execution_result.call_count == 2   # 2回ともLLM判断実行
    assert "商品の売上データが正常に取得されました" in str(result)
    
    print("✅ SQLパラメータ修正テスト成功")
    print(f"ツール呼び出し回数: {mock_connection_manager.call_tool.call_count}")
    print(f"LLM判断回数: {mock_llm_interface.judge_tool_execution_result.call_count}")


if __name__ == "__main__":
    # 単体実行用
    import asyncio
    
    async def run_tests():
        print("=== LLM SQL修正機能シンプルテスト開始 ===")
        
        try:
            print("\n1. LLM判断常時実行テスト")
            await test_llm_judgment_always_executed_simple()
            
            print("\n2. SQLパラメータ修正テスト")
            await test_llm_sql_parameter_correction()
            
            print("\n✅ 全てのテストが成功しました！")
            
        except Exception as e:
            print(f"\n❌ テストが失敗しました: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_tests())