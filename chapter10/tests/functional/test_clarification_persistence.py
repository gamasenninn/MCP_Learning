#!/usr/bin/env python3
"""
CLARIFICATION会話履歴永続化の機能テスト
リファクタリング後に失われたCLARIFICATION応答の会話履歴記録機能をテスト

修正対象:
- CLARIFICATIONへの回答が会話履歴に記録される
- 後で「私の年齢は？」などで参照できる
- セッションクリアで履歴が消えない
"""

import pytest
import pytest_asyncio
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from state_manager import StateManager, TaskState
from conversation_manager import ConversationManager
from config_manager import Config, ConversationConfig


@pytest_asyncio.fixture
async def temp_state_manager():
    """テスト用StateManagerの作成"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        yield state_manager


@pytest.fixture
def mock_config():
    """テスト用設定の作成"""
    return Config(
        conversation=ConversationConfig(
            context_limit=10,
            max_history=50
        )
    )


class TestClarificationPersistence:
    """CLARIFICATION会話履歴永続化テスト"""
    
    @pytest.mark.asyncio
    async def test_state_manager_records_conversation_entries(self, temp_state_manager):
        """StateManagerが会話エントリを正しく記録する"""
        
        state_manager = temp_state_manager
        
        # ユーザーメッセージを追加
        await state_manager.add_conversation_entry("user", "私の年齢に3をかけて100を引く")
        
        # アシスタントメッセージを追加 
        await state_manager.add_conversation_entry("assistant", "あなたの年齢は何歳ですか？")
        
        # ユーザー回答を追加
        await state_manager.add_conversation_entry("user", "65")
        
        # アシスタント最終回答を追加
        await state_manager.add_conversation_entry("assistant", "計算結果は95です")
        
        # 会話履歴を取得して確認
        history = state_manager.get_conversation_context(10)
        
        assert len(history) == 4
        assert history[0]['role'] == 'user'
        assert history[0]['content'] == "私の年齢に3をかけて100を引く"
        assert history[1]['role'] == 'assistant'
        assert history[1]['content'] == "あなたの年齢は何歳ですか？"
        assert history[2]['role'] == 'user'
        assert history[2]['content'] == "65"
        assert history[3]['role'] == 'assistant' 
        assert history[3]['content'] == "計算結果は95です"
    
    @pytest.mark.asyncio
    async def test_conversation_manager_integration(self, temp_state_manager, mock_config):
        """ConversationManagerとStateManagerの統合テスト"""
        
        state_manager = temp_state_manager
        conversation_manager = ConversationManager(state_manager, mock_config)
        
        # ConversationManagerでメッセージを追加
        conversation_manager.add_to_conversation("user", "こんにちは")
        conversation_manager.add_to_conversation("assistant", "こんにちは！")
        
        # StateManagerにも同じ内容を追加（実際のコードで行われる処理）
        await state_manager.add_conversation_entry("user", "こんにちは")
        await state_manager.add_conversation_entry("assistant", "こんにちは！")
        
        # ConversationManagerのサマリー取得
        summary = conversation_manager.get_conversation_summary()
        assert summary["total_messages"] == 2
        assert summary["user_messages"] == 1
        assert summary["assistant_messages"] == 1
        
        # StateManagerの会話履歴取得
        history = state_manager.get_conversation_context(10)
        assert len(history) == 2
        
        # 両方で同じ内容が記録されている
        assert history[0]['content'] == "こんにちは"
        assert history[1]['content'] == "こんにちは！"
    
    @pytest.mark.asyncio
    async def test_clarification_task_workflow(self, temp_state_manager):
        """CLARIFICATIONタスクワークフローのテスト"""
        
        state_manager = temp_state_manager
        
        # 1. 初期ユーザーリクエスト
        await state_manager.add_conversation_entry("user", "私の年齢に3をかけて")
        
        # 2. CLARIFICATIONタスクの作成と実行シミュレーション
        clarification_task = TaskState(
            task_id="clarification_001",
            tool="CLARIFICATION",
            params={
                "question": "あなたの年齢は何歳ですか？",
                "context": "要求: 私の年齢に3をかけて",
                "user_query": "私の年齢に3をかけて"
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        await state_manager.add_pending_task(clarification_task)
        
        # 3. CLARIFICATION質問の記録
        await state_manager.add_conversation_entry("assistant", "あなたの年齢は何歳ですか？")
        
        # 4. ユーザー回答
        await state_manager.add_conversation_entry("user", "30")
        
        # 5. タスク完了
        await state_manager.move_task_to_completed("clarification_001", {"user_response": "30"})
        
        # 6. 最終回答
        await state_manager.add_conversation_entry("assistant", "計算結果: 30 × 3 = 90")
        
        # 検証: 全ての会話が記録されている
        history = state_manager.get_conversation_context(10)
        assert len(history) == 4
        
        # ユーザーの年齢回答「30」が記録されている
        user_messages = [msg for msg in history if msg['role'] == 'user']
        assert len(user_messages) == 2
        assert any(msg['content'] == "30" for msg in user_messages)
        
        # 完了タスクに記録されている
        completed_tasks = state_manager.get_completed_tasks()
        assert len(completed_tasks) == 1
        assert completed_tasks[0].task_id == "clarification_001"
        assert completed_tasks[0].result["user_response"] == "30"
    
    @pytest.mark.asyncio
    async def test_session_persistence_across_operations(self, temp_state_manager):
        """セッション永続化のテスト"""
        
        state_manager = temp_state_manager
        
        # 複数の操作を行う
        await state_manager.add_conversation_entry("user", "最初のメッセージ")
        await state_manager.add_conversation_entry("assistant", "最初の応答")
        
        # セッション情報を取得
        session_before = state_manager.current_session
        
        # さらに操作を追加
        await state_manager.add_conversation_entry("user", "二番目のメッセージ")
        await state_manager.add_conversation_entry("assistant", "二番目の応答")
        
        # セッション情報確認
        session_after = state_manager.current_session
        
        # セッションIDが維持されている
        assert session_before.session_id == session_after.session_id
        
        # 会話履歴が累積されている
        history = state_manager.get_conversation_context(10)
        assert len(history) == 4
        
        # ファイルが実際に作成されている
        assert state_manager.conversation_file.exists()
        assert state_manager.session_file.exists()
        
        # ファイル内容を確認
        with open(state_manager.conversation_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "最初のメッセージ" in content
            assert "二番目のメッセージ" in content
    
    @pytest.mark.asyncio
    async def test_age_information_retrieval_from_history(self, temp_state_manager):
        """会話履歴からの年齢情報取得テスト"""
        
        state_manager = temp_state_manager
        
        # 年齢に関する会話履歴を作成
        conversation_sequence = [
            ("user", "私の年齢に5をかけて"),
            ("assistant", "あなたの年齢は何歳ですか？"),
            ("user", "25"),
            ("assistant", "計算結果: 25 × 5 = 125")
        ]
        
        for role, content in conversation_sequence:
            await state_manager.add_conversation_entry(role, content)
        
        # 後から年齢を問い合わせる状況をシミュレート
        history = state_manager.get_conversation_context(10)
        
        # 履歴から年齢情報「25」を見つけられることを確認
        user_messages = [msg['content'] for msg in history if msg['role'] == 'user']
        assert "25" in user_messages
        
        # 年齢に関連する会話パターンが記録されている
        conversation_text = " ".join([msg['content'] for msg in history])
        assert "年齢" in conversation_text
        assert "25" in conversation_text
        assert "何歳ですか" in conversation_text


class TestConversationFileLogging:
    """会話ログファイル記録のテスト"""
    
    @pytest.mark.asyncio
    async def test_conversation_file_format(self, temp_state_manager):
        """会話ログファイルのフォーマットテスト"""
        
        state_manager = temp_state_manager
        
        # 会話を記録
        await state_manager.add_conversation_entry("user", "テストメッセージ")
        await state_manager.add_conversation_entry("assistant", "テスト応答")
        
        # ファイル内容を確認
        with open(state_manager.conversation_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 正しい形式で記録されている
        assert "[USER]" in content
        assert "[ASSISTANT]" in content
        assert "テストメッセージ" in content
        assert "テスト応答" in content
    
    @pytest.mark.asyncio
    async def test_multiple_conversation_entries_order(self, temp_state_manager):
        """複数の会話エントリの順序テスト"""
        
        state_manager = temp_state_manager
        
        # 順序を意識した会話を記録
        entries = [
            ("user", "1番目のメッセージ"),
            ("assistant", "1番目の応答"),
            ("user", "2番目のメッセージ"),
            ("assistant", "2番目の応答"),
            ("user", "3番目のメッセージ"),
            ("assistant", "3番目の応答")
        ]
        
        for role, content in entries:
            await state_manager.add_conversation_entry(role, content)
        
        # 履歴の順序確認
        history = state_manager.get_conversation_context(10)
        assert len(history) == 6
        
        for i, (expected_role, expected_content) in enumerate(entries):
            assert history[i]['role'] == expected_role
            assert history[i]['content'] == expected_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])