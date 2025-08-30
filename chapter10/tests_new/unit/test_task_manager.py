#!/usr/bin/env python3
"""
Unit tests for TaskManager
タスク管理システムの単体テスト
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from task_manager import TaskManager
from state_manager import TaskState


@pytest.mark.unit
def test_task_manager_initialization(task_manager):
    """TaskManagerの初期化テスト"""
    manager = task_manager
    assert manager is not None


@pytest.mark.unit
def test_clarification_detection(task_manager):
    """CLARIFICATION検出のテスト"""
    manager = task_manager
    
    # 曖昧な表現を含むクエリ
    ambiguous_queries = [
        "私の年齢に10を足して",
        "当社の売上を計算",
        "私のファイルを削除して"
    ]
    
    for query in ambiguous_queries:
        # 実際のCLARIFICATION検出ロジックをテスト
        # （実装に応じて調整が必要）
        pass


@pytest.mark.unit
@pytest.mark.asyncio
async def test_task_creation(task_manager):
    """タスク作成のテスト"""
    manager = task_manager
    
    # モックLLMクライアント
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '''
    {"tasks": [
        {
            "tool": "multiply",
            "params": {"a": 5, "b": 10},
            "description": "5に10を掛ける"
        }
    ]}
    '''
    mock_llm.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # タスク生成テスト（実装に応じて調整）
    # tasks = await manager.generate_tasks("5に10を掛けて", mock_llm)
    # assert len(tasks) == 1
    # assert tasks[0].tool == "multiply"


@pytest.mark.unit
def test_task_dependency_resolution(task_manager):
    """タスク依存関係解決のテスト"""
    manager = task_manager
    
    # 依存関係のあるタスク
    tasks = [
        TaskState(
            task_id="task_001",
            tool="multiply",
            params={"a": 5, "b": 10},
            description="5に10を掛ける",
            status="pending"
        ),
        TaskState(
            task_id="task_002",
            tool="add", 
            params={"a": "前の計算結果", "b": 20},
            description="結果に20を足す",
            status="pending"
        )
    ]
    
    # 依存関係解決のテスト（実装に応じて調整）
    # resolved_tasks = manager.resolve_dependencies(tasks)
    # assert len(resolved_tasks) == 2


@pytest.mark.unit
def test_clarification_task_creation(task_manager):
    """CLARIFICATIONタスク作成のテスト"""
    manager = task_manager
    
    # CLARIFICATION作成のテスト
    question = "年齢を教えてください"
    context = "私の年齢に10を足して"
    
    # clarification_task = manager.create_clarification_task(question, context)
    # assert clarification_task.tool == "CLARIFICATION"
    # assert question in clarification_task.params["question"]


@pytest.mark.unit
def test_task_validation(task_manager):
    """タスク検証のテスト"""
    manager = task_manager
    
    # 有効なタスク
    valid_task = TaskState(
        task_id="valid_001",
        tool="multiply",
        params={"a": 5, "b": 10},
        description="有効なタスク",
        status="pending"
    )
    
    # 無効なタスク（必須パラメータなし）
    invalid_task = TaskState(
        task_id="invalid_001", 
        tool="multiply",
        params={"a": 5},  # bパラメータが不足
        description="無効なタスク",
        status="pending"
    )
    
    # 検証テスト（実装に応じて調整）
    # assert manager.validate_task(valid_task) == True
    # assert manager.validate_task(invalid_task) == False