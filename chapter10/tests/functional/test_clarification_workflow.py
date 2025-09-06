#!/usr/bin/env python3
"""
CLARIFICATIONワークフローの機能テスト
実際のエンドツーエンド処理で会話ログが正しく記録されることを確認
"""

import pytest
import pytest_asyncio
import tempfile
import asyncio
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_agent import MCPAgent
from state_manager import StateManager, TaskState
from task_manager import TaskManager
from conversation_manager import ConversationManager
from connection_manager import ConnectionManager
from config_manager import Config, ConversationConfig


@pytest.fixture
async def mock_mcp_agent_for_clarification():
    """CLARIFICATION専用のMCPAgentモック"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 設定ファイル用の一時ディレクトリ
        config_path = Path(temp_dir) / "config.yaml"
        
        # 設定内容を作成
        config_content = """
display:
  ui_mode: basic
  show_timing: false
  show_thinking: false

llm:
  model: gpt-4o-mini
  temperature: 0.2
  max_completion_tokens: 1000

execution:
  max_retries: 3
  timeout_seconds: 30
  max_tasks: 10

conversation:
  context_limit: 10
  max_history: 50

development:
  verbose: false
"""
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        # MCPAgentを初期化
        agent = MCPAgent(str(config_path))
        
        # LLMクライアントをモック
        mock_llm = AsyncMock()
        agent.llm = mock_llm
        
        # ConnectionManagerをモック
        agent.connection_manager = MagicMock()
        agent.connection_manager.call_tool = AsyncMock()
        agent.connection_manager.format_tools_for_llm = MagicMock(return_value="mocked_tools_info")
        
        # StateManagerを一時ディレクトリに設定
        agent.state_manager.state_dir = Path(temp_dir) / ".mcp_agent"
        
        await agent.initialize()
        
        yield agent


@pytest.mark.functional
@pytest.mark.asyncio
async def test_end_to_end_clarification_logging():
    """エンドツーエンドCLARIFICATIONワークフローのログ記録テスト"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # StateManagerを一時ディレクトリで初期化
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        # ConversationManager、TaskManagerを初期化
        mock_config = Config(
            conversation=ConversationConfig(
                context_limit=10,
                max_history=50
            )
        )
        conversation_manager = ConversationManager(state_manager, mock_config)
        
        mock_llm = AsyncMock()
        task_manager = TaskManager(state_manager)
        
        # === CLARIFICATION処理のフルワークフローをシミュレート ===
        
        # 1. ユーザークエリの受信
        user_query = "私の年齢に３をかけて１００をひいて"
        await state_manager.add_conversation_entry("user", user_query)
        
        # 2. CLARIFICATIONタスクの生成と実行
        clarification_task = TaskState(
            task_id="clarification_test_001",
            tool="CLARIFICATION",
            params={
                "question": "あなたの年齢は何歳ですか？",
                "context": f"要求: {user_query}",
                "user_query": user_query
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        # CLARIFICATIONタスクの実行（修正部分をテスト）
        question_message = await task_manager.execute_clarification_task(clarification_task)
        await state_manager.add_conversation_entry("assistant", question_message)
        
        # 3. ユーザー応答の処理
        user_response = "６５"
        await state_manager.add_conversation_entry("user", user_response)
        
        # CLARIFICATIONタスクを完了状態に移行
        await state_manager.move_task_to_completed(
            clarification_task.task_id, 
            {"user_response": user_response}
        )
        
        # 4. 実際の計算タスクの実行（シミュレート）
        calculation_tasks = [
            {
                "task_id": "calc_001",
                "tool": "multiply", 
                "result": "195.0",
                "description": "65 × 3"
            },
            {
                "task_id": "calc_002",
                "tool": "subtract",
                "result": "95.0", 
                "description": "195 - 100"
            }
        ]
        
        for task in calculation_tasks:
            await state_manager.move_task_to_completed(
                task["task_id"],
                task["result"]
            )
        
        # 5. 最終応答の生成と記録（修正部分をテスト）
        final_response = """計算が完了しました。

年齢65に3を掛けて100を引いた結果：
- 65 × 3 = 195
- 195 - 100 = 95

**答えは95です。**"""
        
        execution_results = [
            {"step": "multiply", "tool": "multiply", "success": True, "result": "195.0"},
            {"step": "subtract", "tool": "subtract", "success": True, "result": "95.0"}
        ]
        
        # ConversationManagerとStateManagerの両方に記録
        conversation_manager.add_to_conversation("assistant", final_response, execution_results)
        await state_manager.add_conversation_entry("assistant", final_response)
        
        # === 検証部分 ===
        
        # 会話ログファイルの存在確認
        conversation_file = state_manager.conversation_file
        assert conversation_file.exists(), "会話ログファイルが作成されていない"
        
        # ファイル内容の読み込み
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # 完全なワークフローが記録されているか確認
        expected_entries = [
            ("[USER]", user_query),
            ("[ASSISTANT]", "確認が必要です"),
            ("[ASSISTANT]", "あなたの年齢は何歳ですか？"),
            ("[USER]", user_response),
            ("[ASSISTANT]", "答えは95です")
        ]
        
        for entry_type, content in expected_entries:
            assert entry_type in log_content, f"{entry_type} エントリがログに記録されていない"
            assert content in log_content, f"期待される内容が記録されていない: {content}"
        
        # エントリ数の確認
        user_entries = log_content.count("[USER]")
        assistant_entries = log_content.count("[ASSISTANT]")
        
        assert user_entries == 2, f"ユーザーエントリが2つ必要だが {user_entries} 個"
        assert assistant_entries == 2, f"アシスタントエントリが2つ必要だが {assistant_entries} 個"
        
        # JSONファイルとの整合性確認
        session_file = state_manager.session_file
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # JSONファイルにも会話が記録されていることを確認
        conversation_context = session_data.get("conversation_context", [])
        assert len(conversation_context) >= 2, "JSONファイルに会話が記録されていない"
        
        # 最初のユーザーメッセージが記録されていることを確認
        user_messages = [entry for entry in conversation_context if entry["role"] == "user"]
        assert any(user_query in msg["content"] for msg in user_messages), \
            "ユーザークエリがJSONファイルに記録されていない"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_skip_command_workflow():
    """skipコマンド処理の機能テスト"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        mock_config = Config(
            conversation=ConversationConfig(
                context_limit=10,
                max_history=50
            )
        )
        conversation_manager = ConversationManager(state_manager, mock_config)
        mock_llm = AsyncMock()
        task_manager = TaskManager(state_manager)
        
        # 1. ユーザークエリ
        user_query = "複利計算をして"
        await state_manager.add_conversation_entry("user", user_query)
        
        # 2. CLARIFICATIONタスクの生成
        clarification_task = TaskState(
            task_id="skip_test_001",
            tool="CLARIFICATION",
            params={
                "question": "複利計算の条件（元本、金利、期間）を教えてください",
                "context": f"要求: {user_query}",
                "user_query": user_query
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        # CLARIFICATIONタスクの実行と記録
        question_message = await task_manager.execute_clarification_task(clarification_task)
        await state_manager.add_conversation_entry("assistant", question_message)
        
        # 3. skipコマンドの処理
        skip_command = "skip"
        await state_manager.add_conversation_entry("user", skip_command)
        
        # skipによるタスク完了処理
        await state_manager.move_task_to_completed(
            clarification_task.task_id,
            {"user_response": "skipped", "skipped": True}
        )
        
        # 4. スキップ後の応答
        skip_response = "質問をスキップしました。会話履歴と文脈から最適な処理を実行します。"
        await state_manager.add_conversation_entry("assistant", skip_response)
        
        # === 検証 ===
        
        conversation_file = state_manager.conversation_file
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # skipワークフローが正しく記録されているか確認
        assert user_query in log_content, "最初のユーザークエリが記録されていない"
        assert "確認が必要です" in log_content, "CLARIFICATIONの質問が記録されていない"
        assert "複利計算の条件" in log_content, "質問内容が記録されていない"
        assert skip_command in log_content, "skipコマンドが記録されていない"
        assert "質問をスキップしました" in log_content, "スキップ応答が記録されていない"
        
        # エントリ数の確認（USER: 2回、ASSISTANT: 2回）
        user_entries = log_content.count("[USER]")
        assistant_entries = log_content.count("[ASSISTANT]")
        
        assert user_entries == 2, f"ユーザーエントリが2つ必要だが {user_entries} 個"
        assert assistant_entries == 2, f"アシスタントエントリが2つ必要だが {assistant_entries} 個"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_conversation_manager_state_manager_sync():
    """ConversationManagerとStateManagerの同期テスト"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        mock_config = Config(
            conversation=ConversationConfig(
                context_limit=10,
                max_history=50
            )
        )
        conversation_manager = ConversationManager(state_manager, mock_config)
        
        # ConversationManagerに複数のエントリを追加
        conversations = [
            ("user", "最初のメッセージ"),
            ("assistant", "最初の応答"),
            ("user", "2番目のメッセージ"),
            ("assistant", "2番目の応答")
        ]
        
        # ConversationManagerに追加
        for role, message in conversations:
            conversation_manager.add_to_conversation(role, message)
        
        # StateManagerにも追加（修正により両方に記録される想定）
        for role, message in conversations:
            await state_manager.add_conversation_entry(role, message)
        
        # ConversationManagerのサマリー取得
        summary = conversation_manager.get_conversation_summary()
        
        # StateManagerの会話コンテキスト取得
        context = state_manager.get_conversation_context(10)
        
        # 両方に同じ数の会話が記録されていることを確認
        assert summary["total_messages"] == 4, "ConversationManagerの会話数が正しくない"
        assert len(context) == 4, "StateManagerの会話数が正しくない"
        
        # 会話ログファイルの内容確認
        conversation_file = state_manager.conversation_file
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # すべてのメッセージが記録されていることを確認
        for role, message in conversations:
            assert message in log_content, f"メッセージが記録されていない: {message}"
        
        # ロール別エントリ数の確認
        user_count = summary["user_messages"]
        assistant_count = summary["assistant_messages"]
        
        assert user_count == 2, f"ユーザーメッセージが2つ必要だが {user_count} 個"
        assert assistant_count == 2, f"アシスタントメッセージが2つ必要だが {assistant_count} 個"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])