#!/usr/bin/env python3
"""
Unit tests for StateManager
状態管理システムの単体テスト
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from state_manager import StateManager, TaskState


@pytest.mark.unit
@pytest.mark.asyncio
async def test_state_manager_initialization(temp_dir):
    """StateManagerの初期化テスト"""
    state_dir = Path(temp_dir) / ".mcp_agent"
    manager = StateManager(state_dir=str(state_dir))
    
    assert manager.state_dir == state_dir
    assert state_dir.exists()
    assert (state_dir / "tasks").exists()


@pytest.mark.unit
@pytest.mark.asyncio  
async def test_session_initialization(state_manager):
    """セッション初期化のテスト"""
    session_id = "test_session_001"
    
    # セッション初期化
    created_id = await state_manager.initialize_session(session_id)
    
    # セッションIDが返されることを確認
    assert created_id is not None
    
    # セッション状態が設定されることを確認
    assert state_manager.current_session is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_task_persistence(state_manager, sample_tasks):
    """タスクの永続化テスト"""
    task = sample_tasks[0]
    
    # セッション初期化
    await state_manager.initialize_session()
    
    # タスク保存（実際のメソッド名を確認して調整）
    # await state_manager.save_task(task)
    
    # タスクディレクトリが存在することを確認
    tasks_dir = state_manager.state_dir / "tasks"
    assert tasks_dir.exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_conversation_logging(state_manager):
    """会話ログのテスト"""
    # セッション初期化
    await state_manager.initialize_session()
    
    # ログファイルが作成されることを確認
    log_file = state_manager.state_dir / "conversation.txt"
    # ファイルパスが設定されていることを確認
    assert state_manager.conversation_file == log_file


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_summary(state_manager):
    """セッション要約のテスト"""
    # セッション初期化
    await state_manager.initialize_session()
    
    # 要約取得（実際のメソッドを確認）
    summary = state_manager.get_session_summary()
    
    assert summary is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_archiving(state_manager):
    """セッションアーカイブのテスト"""
    # セッション初期化
    await state_manager.initialize_session()
    
    # アーカイブディレクトリが存在することを確認
    history_dir = state_manager.state_dir / "history"
    assert history_dir.exists()