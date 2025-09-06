#!/usr/bin/env python3
"""
Error Retry Mechanism Integration Tests
エラーリトライ機能の統合テスト

TaskExecutorとErrorHandlerの統合によるエラー処理とリトライ機能をテスト

## テスト対象の機能
1. 基本的なリトライ機能（ErrorHandlerなし）
2. LLMによるエラー判断とパラメータ修正
3. 最大リトライ回数の制御

## 重要な修正内容（2025-08-31）
Phase 3リファクタリングで以下の機能が統合されました：
- TaskExecutorのexecute_tool_with_retry()にErrorHandler連携を追加
- LLM判断によるパラメータ自動修正機能
- 賢いエラー処理によるユーザーエクスペリエンス向上

これらのテストにより、リトライ機能の品質と信頼性が保証されます。
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, call, Mock
import json
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from task_executor import TaskExecutor
from error_handler import ErrorHandler
from state_manager import TaskState
from utils import safe_str


@pytest.mark.integration  
@pytest.mark.asyncio
async def test_basic_retry_functionality(temp_dir, mock_config, mock_llm_client):
    """基本的なリトライ機能のテスト"""
    from task_manager import TaskManager
    from connection_manager import ConnectionManager
    from state_manager import StateManager
    from display_manager import DisplayManager
    from error_handler import ErrorHandler
    
    # 必要なモックを設定
    mock_task_manager = MagicMock()
    mock_connection_manager = MagicMock()
    mock_connection_manager.call_tool = AsyncMock()
    mock_state_manager = MagicMock()
    mock_display_manager = MagicMock()
    mock_error_handler = MagicMock()
    
    # TaskExecutorを直接作成
    task_executor = TaskExecutor(
        task_manager=mock_task_manager,
        connection_manager=mock_connection_manager,
        state_manager=mock_state_manager,
        display_manager=mock_display_manager,
        llm_interface=Mock(),  # LLMInterfaceをモック
        config=mock_config,
        error_handler=None,  # ErrorHandlerなしでテスト
        verbose=True
    )
    
    # 3回エラー後に成功するパターンをテスト
    mock_connection_manager.call_tool.side_effect = [
        Exception("Error 1"),
        Exception("Error 2"), 
        Exception("Error 3"),
        "Success"
    ]
    
    result = await task_executor.execute_tool_with_retry(
        tool="test_tool",
        params={"param": "test"}, 
        description="基本リトライテスト"
    )
    
    # 検証: 4回目で成功
    assert mock_connection_manager.call_tool.call_count == 4
    assert result == "Success"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_error_correction(temp_dir, mock_config, mock_llm_client):
    """LLMによるエラー修正機能のテスト"""
    from task_manager import TaskManager
    from connection_manager import ConnectionManager
    from state_manager import StateManager
    from display_manager import DisplayManager
    from error_handler import ErrorHandler
    
    # 必要なモックを設定
    mock_task_manager = MagicMock()
    mock_connection_manager = MagicMock()
    mock_connection_manager.call_tool = AsyncMock()
    mock_state_manager = MagicMock()
    mock_display_manager = MagicMock()
    
    # LLMInterfaceの作成とモック
    mock_llm_interface = Mock()
    
    # ErrorHandlerを作成
    error_handler = ErrorHandler(
        config=mock_config,
        llm_interface=mock_llm_interface,
        verbose=True
    )
    
    # TaskExecutorを作成（ErrorHandler付き）
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
    
    # 1回目はエラー、2回目は成功
    mock_connection_manager.call_tool.side_effect = [
        Exception("Parameter error"),
        "Success with corrected params"
    ]
    
    # LLMInterfaceのjudge_tool_execution_resultメソッドをモック（段階的レスポンス）
    llm_responses = [
        {
            "is_success": False,
            "needs_retry": True,
            "error_reason": "パラメータエラーが発生しました",
            "corrected_params": {"param": "corrected_value"},
            "processed_result": "パラメータを修正しました",
            "summary": "パラメータ修正によるリトライ"
        },
        {
            "is_success": True,
            "needs_retry": False,
            "processed_result": "Success with corrected params",
            "summary": "修正成功"
        }
    ]
    
    mock_llm_interface.judge_tool_execution_result = AsyncMock(side_effect=llm_responses)
    
    result = await task_executor.execute_tool_with_retry(
        tool="test_tool",
        params={"param": "wrong_value"}, 
        description="LLM修正テスト"
    )
    
    # 検証: 統一化により全結果をLLM判断するため、呼び出し回数が増加
    # 1回目: エラー→LLM判断でリトライ指示
    # 2回目以降: LLM判断で成功判定まで継続
    assert mock_connection_manager.call_tool.call_count >= 2
    assert result == "Success with corrected params"
    
    # LLM判断が呼ばれたことを確認
    assert mock_llm_interface.judge_tool_execution_result.called


@pytest.mark.integration
@pytest.mark.asyncio
async def test_max_retries_exceeded(temp_dir, mock_config, mock_llm_client):
    """最大リトライ回数超過のテスト"""
    from error_handler import ErrorHandler
    
    # 必要なモックを設定
    mock_task_manager = MagicMock()
    mock_connection_manager = MagicMock()
    mock_connection_manager.call_tool = AsyncMock()
    mock_state_manager = MagicMock()
    mock_display_manager = MagicMock()
    
    # TaskExecutorを作成（ErrorHandlerなし、シンプルなリトライのみ）
    task_executor = TaskExecutor(
        task_manager=mock_task_manager,
        connection_manager=mock_connection_manager,
        state_manager=mock_state_manager,
        display_manager=mock_display_manager,
        llm_interface=Mock(),  # LLMInterfaceをモック
        config=mock_config,
        error_handler=None,
        verbose=True
    )
    
    # 常にエラーを返す
    mock_connection_manager.call_tool.side_effect = Exception("Persistent error")
    
    # エラーが発生することを確認
    with pytest.raises(Exception) as exc_info:
        await task_executor.execute_tool_with_retry(
            tool="test_tool",
            params={"param": "test"},
            description="最大リトライテスト"
        )
    
    # 最大リトライ回数（3回）+1の計4回試行されることを確認
    assert mock_connection_manager.call_tool.call_count == 4
    assert "Persistent error" in str(exc_info.value)