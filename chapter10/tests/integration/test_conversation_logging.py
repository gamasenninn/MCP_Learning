#!/usr/bin/env python3
"""
会話ログ記録の統合テスト
CLARIFICATIONタスクの質問と最終応答が正しく記録されることを確認
"""

import pytest
import pytest_asyncio
import tempfile
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_agent import MCPAgent
from state_manager import StateManager, TaskState
from task_manager import TaskManager
from conversation_manager import ConversationManager
from config_manager import Config, ConversationConfig


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clarification_question_logged():
    """CLARIFICATIONタスクの質問が会話ログに記録されるかテスト"""
    
    # 一時ディレクトリでStateManagerを初期化
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        # TaskManagerの初期化
        mock_llm = AsyncMock()
        task_manager = TaskManager(state_manager)
        
        # CLARIFICATIONタスクを作成
        clarification_task = TaskState(
            task_id="test_clarification_001",
            tool="CLARIFICATION",
            params={
                "question": "あなたの年齢は何歳ですか？",
                "context": "要求: 私の年齢に３をかけて１００をひいて",
                "user_query": "私の年齢に３をかけて１００をひいて"
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        # CLARIFICATIONタスクを実行（質問を生成）
        question_message = await task_manager.execute_clarification_task(clarification_task)
        
        # StateManagerに質問を記録（実際の修正部分をテスト）
        await state_manager.add_conversation_entry("assistant", question_message)
        
        # 会話ログファイルを読み込んで確認
        conversation_file = state_manager.conversation_file
        assert conversation_file.exists(), "会話ログファイルが作成されていない"
        
        # ファイル内容を確認
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # 質問内容が記録されているか確認
        assert "[ASSISTANT]" in log_content, "ASSISTANTのエントリがログに記録されていない"
        assert "確認が必要です" in log_content, "質問メッセージが記録されていない"
        assert "あなたの年齢は何歳ですか？" in log_content, "質問内容が記録されていない"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_final_response_logged():
    """最終応答が会話ログに記録されるかテスト"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        # ConversationManagerの初期化
        mock_config = Config(
            conversation=ConversationConfig(
                context_limit=10,
                max_history=50
            )
        )
        conversation_manager = ConversationManager(state_manager, mock_config)
        
        # 最終応答をシミュレート
        final_response = """計算結果をお知らせします。

年齢65歳に3を掛けて100を引いた結果は：
- 65 × 3 = 195
- 195 - 100 = 95

最終的な答えは **95** です。"""
        
        execution_results = [
            {"step": "multiply", "tool": "multiply", "success": True, "result": "195.0"},
            {"step": "subtract", "tool": "subtract", "success": True, "result": "95.0"}
        ]
        
        # ConversationManagerとStateManagerの両方に記録（修正部分をテスト）
        conversation_manager.add_to_conversation("assistant", final_response, execution_results)
        await state_manager.add_conversation_entry("assistant", final_response)
        
        # 会話ログファイルを確認
        conversation_file = state_manager.conversation_file
        assert conversation_file.exists(), "会話ログファイルが作成されていない"
        
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # 最終応答が記録されているか確認
        assert "[ASSISTANT]" in log_content, "ASSISTANTのエントリがログに記録されていない"
        assert "最終的な答えは" in log_content, "最終応答が記録されていない"
        assert "95" in log_content, "計算結果が記録されていない"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_clarification_workflow():
    """完全なCLARIFICATIONワークフローのテスト"""
    
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
        
        # 1. ユーザーのクエリを記録
        user_query = "私の年齢に３をかけて１００をひいて"
        await state_manager.add_conversation_entry("user", user_query)
        
        # 2. CLARIFICATIONタスクの質問を記録
        clarification_task = TaskState(
            task_id="test_workflow_001",
            tool="CLARIFICATION",
            params={
                "question": "あなたの年齢は何歳ですか？",
                "context": f"要求: {user_query}",
                "user_query": user_query
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        question_message = await task_manager.execute_clarification_task(clarification_task)
        await state_manager.add_conversation_entry("assistant", question_message)
        
        # 3. ユーザーの回答を記録
        user_response = "６５"
        await state_manager.add_conversation_entry("user", user_response)
        
        # 4. 最終応答を記録
        final_response = "計算完了しました。65 × 3 - 100 = 95です。"
        await state_manager.add_conversation_entry("assistant", final_response)
        
        # 5. 会話ログの完全性を確認
        conversation_file = state_manager.conversation_file
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # 会話の流れが正しく記録されているか確認
        lines = [line.strip() for line in log_content.split('\n') if line.strip()]
        
        # USER → ASSISTANT(質問) → USER(回答) → ASSISTANT(結果) の順序を確認
        user_entries = [line for line in lines if "[USER]" in line]
        assistant_entries = [line for line in lines if "[ASSISTANT]" in line]
        
        assert len(user_entries) == 2, f"ユーザーエントリが2つ必要だが {len(user_entries)} 個"
        assert len(assistant_entries) == 2, f"アシスタントエントリが2つ必要だが {len(assistant_entries)} 個"
        
        # 内容の確認
        assert user_query in log_content, "最初のユーザークエリが記録されていない"
        assert "確認が必要です" in log_content, "CLARIFICATIONの質問が記録されていない"
        assert user_response in log_content, "ユーザーの回答が記録されていない"
        assert "計算完了しました" in log_content, "最終応答が記録されていない"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_clarifications():
    """複数のCLARIFICATIONタスクが正しく記録されるかテスト"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        mock_llm = AsyncMock()
        task_manager = TaskManager(state_manager)
        
        # 複数のCLARIFICATIONタスクを順次実行
        clarifications = [
            {
                "question": "あなたの年齢は何歳ですか？",
                "context": "年齢計算のため"
            },
            {
                "question": "複利計算の期間は何年ですか？",
                "context": "複利計算のため"
            }
        ]
        
        for i, clarif in enumerate(clarifications):
            # CLARIFICATIONタスクを作成・実行
            task = TaskState(
                task_id=f"test_multi_{i+1:03d}",
                tool="CLARIFICATION",
                params=clarif,
                description="ユーザーに確認",
                status="pending"
            )
            
            question_message = await task_manager.execute_clarification_task(task)
            await state_manager.add_conversation_entry("assistant", question_message)
            
            # ユーザー応答もシミュレート
            user_responses = ["３０", "１０年"]
            await state_manager.add_conversation_entry("user", user_responses[i])
        
        # ログの内容を確認
        conversation_file = state_manager.conversation_file
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # 両方のCLARIFICATIONが記録されているか確認
        assert "年齢は何歳ですか" in log_content, "最初のCLARIFICATIONが記録されていない"
        assert "期間は何年ですか" in log_content, "2番目のCLARIFICATIONが記録されていない"
        assert "３０" in log_content, "最初の回答が記録されていない"
        assert "１０年" in log_content, "2番目の回答が記録されていない"
        
        # エントリ数の確認
        assistant_entries = log_content.count("[ASSISTANT]")
        user_entries = log_content.count("[USER]")
        
        assert assistant_entries == 2, f"アシスタントエントリが2つ必要だが {assistant_entries} 個"
        assert user_entries == 2, f"ユーザーエントリが2つ必要だが {user_entries} 個"


@pytest.mark.integration
@pytest.mark.asyncio 
async def test_no_tool_responses_logged():
    """NO_TOOLタイプの応答も正しく記録されるかテスト"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        
        # NO_TOOLタイプの応答をシミュレート
        no_tool_responses = [
            "こんにちは！何かお手伝いできることはありますか？",
            "私の名前はガーコです！",
            "あなたの名前はサトシですね！"
        ]
        
        for response in no_tool_responses:
            await state_manager.add_conversation_entry("assistant", response)
        
        # ログファイルを確認
        conversation_file = state_manager.conversation_file
        with open(conversation_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # すべてのNO_TOOL応答が記録されているか確認
        for response in no_tool_responses:
            assert response in log_content, f"NO_TOOL応答が記録されていない: {response}"
        
        # エントリ数の確認
        assistant_entries = log_content.count("[ASSISTANT]")
        assert assistant_entries == len(no_tool_responses), \
            f"アシスタントエントリが{len(no_tool_responses)}個必要だが {assistant_entries} 個"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])