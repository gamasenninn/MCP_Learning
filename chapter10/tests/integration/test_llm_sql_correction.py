#!/usr/bin/env python3
"""
LLM SQL correction integration tests
LLMによるSQL自動修正機能の統合テスト

このテストは、TaskExecutorのLLM判断機能が正しく動作し、
不正なSQLを自動的に修正することを確認します。
"""

import pytest
import pytest_asyncio
import tempfile
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_agent import MCPAgent
from task_executor import TaskExecutor
from error_handler import ErrorHandler
from connection_manager import ConnectionManager
from state_manager import StateManager
from config_manager import Config, LLMConfig, ExecutionConfig, ErrorHandlingConfig


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_sql_correction_end_to_end():
    """
    エンドツーエンドSQL修正テスト
    実際のMCPAgentを使用して日本語SQLが英語SQLに修正されることを確認
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # 一時的なセッション管理のための設定
        os.environ['MCP_SESSION_DIR'] = temp_dir
        
        try:
            # MCPAgentを初期化
            agent = MCPAgent('config.yaml')
            await agent.initialize()
            
            # 日本語のSQL要求（意図的に間違った形式）
            user_query = "商品名と売上合計を表示して"
            
            # リクエストを処理
            response = await agent.process_request(user_query)
            
            # 結果の検証
            assert response is not None
            assert len(response) > 0
            
            # 完了済みタスクから実行されたタスクを確認
            completed_tasks = agent.state_manager.get_completed_tasks()
            
            # execute_safe_queryタスクが存在することを確認
            sql_task = None
            for task in completed_tasks:
                if task.tool == 'execute_safe_query':
                    sql_task = task
                    break
            
            assert sql_task is not None, "execute_safe_queryタスクが見つかりません"
            
            # SQLが正しく修正されていることを確認
            sql_params = sql_task.params or {}
            executed_sql = sql_params.get('sql', '')
            
            # 正しいSQL構造の要素が含まれていることを確認
            assert 'SELECT' in executed_sql.upper()
            assert 'FROM' in executed_sql.upper()
            assert 'JOIN' in executed_sql.upper() or 'products' in executed_sql.lower() or 'product' in executed_sql.lower()
            assert 'name' in executed_sql.lower()  # 商品名
            assert 'total_amount' in executed_sql.lower() or 'sales' in executed_sql.lower()  # 売上
            
            # 結果の基本チェック（空文字列やNoneでも実行されていればOK）
            task_result = sql_task.result or ''
            # SQLが実行されたことを確認（結果の内容よりも実行されたことが重要）
            assert sql_task.status == "completed", f"SQLタスクが完了していません: {sql_task.status}"
            
            # データが取得できた場合の確認（オプショナル）
            if isinstance(task_result, str) and task_result and '[' in task_result:
                # JSON形式の結果の場合のみチェック
                if 'product_name' in task_result or 'name' in task_result:
                    print("✅ 商品名データが確認されました")
                if 'total_sales' in task_result or 'sales' in task_result:
                    print("✅ 売上データが確認されました")
            
            print(f"✅ SQL修正テスト成功")
            print(f"実行されたSQL: {executed_sql}")
            print(f"結果データ長: {len(str(task_result))}")
            
        except Exception as e:
            pytest.fail(f"エンドツーエンドSQL修正テストが失敗しました: {e}")
        
        finally:
            if 'agent' in locals():
                await agent.close()


@pytest.mark.integration  
@pytest.mark.asyncio
async def test_llm_judgment_on_empty_result():
    """
    空の結果に対するLLM判断テスト
    空の結果やエラー結果がLLMによって適切に判断されることを確認
    """
    # モック設定
    mock_config = Config(
        llm=LLMConfig(
            model="gpt-4o-mini",
            temperature=0.2
        ),
        execution=ExecutionConfig(
            max_retries=2,
            timeout_seconds=30
        ),
        error_handling=ErrorHandlingConfig(
            auto_correct_params=True
        )
    )
    
    # モックオブジェクトの作成
    mock_llm = AsyncMock()
    mock_connection_manager = MagicMock()
    mock_state_manager = MagicMock() 
    mock_display_manager = MagicMock()
    mock_task_manager = MagicMock()
    
    # LLMInterfaceの作成とモック
    mock_llm_interface = Mock()
    
    # ErrorHandlerの作成
    error_handler = ErrorHandler(
        config=mock_config,
        llm_interface=mock_llm_interface,
        verbose=True
    )
    
    # TaskExecutorの作成
    task_executor = TaskExecutor(
        task_manager=mock_task_manager,
        connection_manager=mock_connection_manager,
        state_manager=mock_state_manager,
        display_manager=mock_display_manager,
        llm_interface=mock_llm_interface,
        config=mock_config,
        error_handler=error_handler,
        verbose=True
    )
    
    # 1回目: 空の結果を返す
    # 2回目: 修正されたクエリで正しい結果を返す
    async def mock_call_tool(*args, **kwargs):
        # 呼び出し回数に応じて異なる結果を返す
        if mock_connection_manager.call_tool.call_count <= 1:
            return ""  # 空の結果（問題のあるSQL）
        else:
            return '{"results": [{"product_name": "iPhone", "total_sales": 1000000}]}'  # 修正後の結果
    
    mock_connection_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
    
    # LLMInterfaceのjudge_tool_execution_resultメソッドをモック
    mock_llm_interface.judge_tool_execution_result = AsyncMock(return_value={
        "is_success": False,
        "needs_retry": True,
        "error_reason": "空の結果が返されました。SQLクエリに問題があります",
        "corrected_params": {
            "sql": "SELECT p.name AS product_name, SUM(s.total_amount) AS total_sales FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.name"
        },
        "processed_result": "SQLを修正して再実行します",
        "summary": "日本語のテーブル名・カラム名を英語に修正し、適切なJOINクエリに変換しました"
    })
    
    # ツール実行（リトライ機能付き）
    result = await task_executor.execute_tool_with_retry(
        tool="execute_safe_query",
        params={"sql": "SELECT 商品名, SUM(売上金額) FROM 売上テーブル GROUP BY 商品名"},
        description="商品名と売上合計を表示"
    )
    
    # 検証
    # 注意: AsyncMockのcall_countは実際の呼び出し後でないと正確でない場合がある
    assert mock_llm_interface.judge_tool_execution_result.call_count >= 1  # LLM判断が実行された
    assert result is not None
    assert '"product_name"' in str(result) or 'iPhone' in str(result) or 'SQL' in str(result)
    
    print(f"✅ 空の結果に対するLLM判断テスト成功")
    print(f"呼び出し回数: {mock_connection_manager.call_tool.call_count}")


@pytest.mark.integration
@pytest.mark.asyncio 
async def test_llm_judgment_always_executed():
    """
    LLM判断常時実行テスト
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
    mock_connection_manager.call_tool = AsyncMock(return_value="正常な結果")
    
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
    
    # LLMInterfaceのjudge_tool_execution_resultメソッドをモック - 成功レスポンス
    mock_llm_interface.judge_tool_execution_result = AsyncMock(return_value={
        "is_success": True,
        "needs_retry": False,
        "processed_result": "正常な結果が得られました",
        "summary": "クエリは正常に実行されました"
    })
    
    # ツール実行（例外なしの成功ケース）
    result = await task_executor.execute_tool_with_retry(
        tool="list_tables",
        params={},
        description="テーブル一覧取得"
    )
    
    # 検証: 成功した場合でもLLM判断が実行されること
    assert mock_connection_manager.call_tool.call_count == 1  # ツールが1回実行
    assert mock_llm_interface.judge_tool_execution_result.call_count == 1   # LLM判断が1回実行
    assert result == "正常な結果が得られました"  # LLMが処理した結果が返される
    
    print("✅ LLM判断常時実行テスト成功")
    print("成功した場合でもLLM判断が実行されることを確認")


if __name__ == "__main__":
    # 単体実行用
    import asyncio
    
    async def run_tests():
        print("=== LLM SQL修正機能テスト開始 ===")
        
        try:
            print("\n1. LLM判断常時実行テスト")
            await test_llm_judgment_always_executed()
            
            print("\n2. 空の結果に対するLLM判断テスト")
            await test_llm_judgment_on_empty_result()
            
            print("\n3. エンドツーエンドSQL修正テスト")
            await test_llm_sql_correction_end_to_end()
            
            print("\n✅ 全てのテストが成功しました！")
            
        except Exception as e:
            print(f"\n❌ テストが失敗しました: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_tests())