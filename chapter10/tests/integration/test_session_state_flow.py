#!/usr/bin/env python3
"""
セッション状態フローの統合テスト
CLARIFICATION → 実行 → 新リクエスト → 履歴参照の完全フローをテスト

修正対象:
- セッションクリアによる会話履歴消失の防止
- 複数リクエストでの状態継続
- CLARIFICATIONとタスク実行の完全な統合
"""

import pytest
import pytest_asyncio
import tempfile
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from mcp_agent import MCPAgent
from state_manager import StateManager, TaskState, SessionState
from task_manager import TaskManager
from conversation_manager import ConversationManager
from connection_manager import ConnectionManager
from task_executor import TaskExecutor
from config_manager import Config


@pytest_asyncio.fixture
async def integrated_agent():
    """実際に近い統合MCPAgent"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
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
  max_retries: 2
  timeout_seconds: 30
  max_tasks: 5

conversation:
  context_limit: 20
  save_logs: true
"""
        config_path.write_text(config_content)
        
        # 実際のStateManagerを使用（一部機能はモック）
        session_dir = Path(temp_dir) / ".mcp_agent"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        state_manager = StateManager(str(session_dir))
        await state_manager.initialize_session()
        
        # ConnectionManagerをモック
        connection_manager = MagicMock(spec=ConnectionManager)
        connection_manager.format_tools_for_llm.return_value = """
Available tools:
- multiply(a, b): 数値の掛け算
- subtract(a, b): 数値の引き算  
- get_weather(location): 天気取得
"""
        connection_manager.call_tool = AsyncMock()
        
        # LLMクライアントをモック
        llm_client = AsyncMock()
        
        # MCPAgentを初期化
        agent = MCPAgent()
        agent.state_manager = state_manager
        agent.connection_manager = connection_manager
        agent.llm = llm_client
        
        # 設定をロード  
        from config_manager import ConversationConfig
        agent.config = Config(
            conversation=ConversationConfig(
                context_limit=20,
                max_history=100
            )
        )
        
        # TaskManagerとConversationManagerを初期化
        task_manager = TaskManager(state_manager)
        conversation_manager = ConversationManager(state_manager, agent.config)
        
        agent.task_manager = task_manager
        agent.conversation_manager = conversation_manager
        
        # TaskExecutorも設定
        from display_manager import DisplayManager
        from error_handler import ErrorHandler
        
        display_manager = MagicMock(spec=DisplayManager)
        error_handler = MagicMock(spec=ErrorHandler)
        
        task_executor = TaskExecutor(
            task_manager=task_manager,
            connection_manager=connection_manager,
            state_manager=state_manager,
            display_manager=display_manager,
            llm_interface=Mock(),  # LLMInterfaceをモック
            config=agent.config,
            error_handler=error_handler,
            verbose=False
        )
        
        agent.task_executor = task_executor
        
        yield agent


class TestSessionStateFlow:
    """セッション状態フロー統合テスト"""
    
    @pytest.mark.asyncio
    async def test_complete_clarification_to_execution_flow(self, integrated_agent):
        """CLARIFICATION → 実行 → 新リクエスト → 履歴参照の完全フロー"""
        
        agent = integrated_agent
        
        # ステップ1: 初回リクエスト（CLARIFICATION要求）
        def mock_determine_execution_type(user_query, recent_context, tools_info):
            # 最初のリクエストの場合はCLARIFICATION
            if "私の年齢に3をかけて100を引く" in user_query:
                return {
                    "type": "CLARIFICATION", 
                    "clarification": {"question": "あなたの年齢は何歳ですか？"}, 
                    "reason": "年齢情報が不明です"
                }
            # CLARIFICATION応答の場合はTOOL（ただし実際には_handle_pending_tasksで処理される）
            else:
                return {
                    "type": "TOOL",
                    "reason": "計算実行"
                }
        
        agent.llm_interface.determine_execution_type = AsyncMock(side_effect=mock_determine_execution_type)
        
        result1 = await agent.process_request("私の年齢に3をかけて100を引く")
        
        # CLARIFICATIONメッセージが表示される
        assert "あなたの年齢は何歳ですか？" in result1
        
        # 会話履歴にユーザーリクエストが記録されている
        history = agent.state_manager.get_conversation_context(10)
        user_entries = [entry for entry in history if entry['role'] == 'user']
        assert len(user_entries) >= 1
        assert user_entries[0]['content'] == "私の年齢に3をかけて100を引く"
        
        # ステップ2: CLARIFICATIONへの回答
        # タスクリスト生成のLLM応答をモック
        agent.llm_interface.generate_task_list = AsyncMock(return_value=[
            {"tool": "multiply", "params": {"a": 65, "b": 3}, "description": "年齢65に3をかける"},
            {"tool": "subtract", "params": {"a": "{{前の結果}}", "b": 100}, "description": "前の結果から100を引く"}
        ])
        
        # ツール実行結果をモック
        async def mock_call_tool(tool_name, params):
            if tool_name == "multiply":
                return {"result": 195}
            elif tool_name == "subtract":
                return {"result": 95}
            return {"result": "unknown"}
        
        agent.connection_manager.call_tool.side_effect = mock_call_tool
        
        # LLM判断（成功）をモック
        agent.llm_interface.judge_tool_execution_result = AsyncMock(return_value={
            "is_success": True, 
            "needs_retry": False, 
            "processed_result": "計算が正常に完了: 95",
            "summary": "計算が正常に完了"
        })
        
        result2 = await agent.process_request("65")
        
        # 計算結果が含まれている
        assert "95" in result2
        
        # 会話履歴に年齢回答が記録されている
        history = agent.state_manager.get_conversation_context(10)
        user_entries = [entry for entry in history if entry['role'] == 'user']
        assert len(user_entries) >= 2
        assert any(entry['content'] == "65" for entry in user_entries)
        
        # ステップ3: 年齢を問い合わせる新リクエスト
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "NO_TOOL", 
            "response": "あなたの年齢は65歳です。", 
            "reason": "会話履歴から年齢情報を確認"
        })
        
        result3 = await agent.process_request("私の年齢は？")
        
        # 履歴から年齢を正しく回答
        assert "65歳" in result3
        
        # 会話履歴が累積されている（3回のユーザー入力）
        history = agent.state_manager.get_conversation_context(20)
        user_entries = [entry for entry in history if entry['role'] == 'user']
        assert len(user_entries) >= 3
    
    @pytest.mark.asyncio
    async def test_session_state_persistence_across_requests(self, integrated_agent):
        """複数リクエストでセッション状態が維持される"""
        
        agent = integrated_agent
        
        # 初期状態確認
        initial_session = agent.state_manager.current_session
        initial_session_id = initial_session.session_id if initial_session else None
        
        # リクエスト1 - LLMInterfaceのdetermine_execution_typeをモック
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "NO_TOOL", 
            "response": "こんにちは！", 
            "reason": "挨拶"
        })
        
        await agent.process_request("こんにちは")
        
        session_after_req1 = agent.state_manager.current_session
        
        # リクエスト2 - LLMInterfaceのdetermine_execution_typeをモック  
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "NO_TOOL", 
            "response": "今日は良い天気ですね", 
            "reason": "天候について"
        })
        
        await agent.process_request("今日はいい天気ですね")
        
        session_after_req2 = agent.state_manager.current_session
        
        # セッションIDが維持されている
        assert session_after_req1.session_id == session_after_req2.session_id
        
        # 会話履歴が累積されている
        history = agent.state_manager.get_conversation_context(10)
        user_entries = [entry for entry in history if entry['role'] == 'user']
        assert len(user_entries) == 2
        
        contents = [entry['content'] for entry in user_entries]
        assert "こんにちは" in contents
        assert "今日はいい天気ですね" in contents
    
    @pytest.mark.asyncio
    async def test_task_completion_state_management(self, integrated_agent):
        """タスク完了状態の管理"""
        
        agent = integrated_agent
        
        # determine_execution_type: TOOLと判定
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "TOOL", 
            "reason": "計算ツールが必要"
        })
        
        # タスク実行を伴うリクエスト
        agent.llm_interface.generate_task_list = AsyncMock(return_value=[
            {"tool": "multiply", "params": {"a": 10, "b": 5}, "description": "10に5をかける"}
        ])
        
        # ツール実行結果をモック
        agent.connection_manager.call_tool = AsyncMock(return_value={"result": 50})
        
        # LLM判断をモック
        agent.llm_interface.judge_tool_execution_result = AsyncMock(return_value={
            "is_success": True, 
            "needs_retry": False, 
            "processed_result": "計算完了: 50",
            "summary": "計算完了"
        })
        
        await agent.process_request("10に5をかけて")
        
        # 完了タスクが記録されている
        completed_tasks = agent.state_manager.get_completed_tasks()
        assert len(completed_tasks) >= 1
        
        # 保留タスクは空
        pending_tasks = agent.state_manager.get_pending_tasks()
        # CLARIFICATIONでない限り空であるべき
        non_clarification_pending = [
            task for task in pending_tasks 
            if task.tool != "CLARIFICATION"
        ]
        assert len(non_clarification_pending) == 0
    
    @pytest.mark.asyncio
    async def test_conversation_context_in_llm_calls(self, integrated_agent):
        """LLM呼び出し時に会話履歴が参照される"""
        
        agent = integrated_agent
        
        # 最初のリクエスト - LLMInterfaceのdetermine_execution_typeをモック
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "NO_TOOL", 
            "response": "了解しました", 
            "reason": "確認"
        })
        
        await agent.process_request("私の名前は田中です")
        
        # 2番目のリクエスト - LLMInterfaceのdetermine_execution_typeをモック
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "NO_TOOL", 
            "response": "田中さん、こんにちは！", 
            "reason": "名前を覚えています"
        })
        
        await agent.process_request("私の名前は？")
        
        # LLM呼び出し時に会話履歴が含まれていることを確認
        llm_calls = agent.llm_interface.determine_execution_type.call_args_list
        
        # 最低1回はLLMが呼ばれている
        assert len(llm_calls) >= 1
        
        # 最後の呼び出しで会話履歴が参照されている - LLMInterfaceでは引数の構造が異なる
        # determine_execution_typeは(user_query, recent_context, tools_info)を受け取る
        last_call = llm_calls[-1]
        call_args = last_call[0]  # args
        
        if len(call_args) >= 2:
            recent_context = call_args[1]  # recent_context parameter
            # 会話履歴に「田中」が含まれているはず
            assert "田中" in recent_context
    
    @pytest.mark.asyncio 
    async def test_error_recovery_with_session_preservation(self, integrated_agent):
        """エラー発生時もセッション状態が保持される"""
        
        agent = integrated_agent
        
        # 正常なリクエスト
        agent.llm.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content='{"type": "NO_TOOL", "response": "正常処理", "reason": "OK"}'))
        ]
        
        await agent.process_request("こんにちは")
        
        # エラーを発生させるリクエスト
        agent.llm.chat.completions.create.side_effect = Exception("LLM接続エラー")
        
        try:
            await agent.process_request("エラーを起こして")
        except Exception:
            pass  # エラーは無視
        
        # エラー後も会話履歴は保持されている
        history = agent.state_manager.get_conversation_context(10)
        user_entries = [entry for entry in history if entry['role'] == 'user']
        
        # 少なくとも最初のリクエストは記録されている
        assert len(user_entries) >= 1
        assert any(entry['content'] == "こんにちは" for entry in user_entries)


class TestRegressionPrevention:
    """リグレッション防止テスト"""
    
    @pytest.mark.asyncio
    async def test_clarification_response_not_lost(self, integrated_agent):
        """CLARIFICATIONへの回答が消失しないことを確認（リグレッション防止）"""
        
        agent = integrated_agent
        
        # CLARIFICATION要求 - LLMInterfaceのdetermine_execution_typeをモック
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "CLARIFICATION", 
            "clarification": {"question": "何歳ですか？"}, 
            "reason": "年齢不明"
        })
        
        result1 = await agent.process_request("年齢に関する計算をして")
        assert "何歳ですか？" in result1
        
        # 回答 - generate_task_listをモック
        agent.llm_interface.generate_task_list = AsyncMock(return_value=[
            {"tool": "multiply", "params": {"a": 30, "b": 2}, "description": "年齢30に2をかける"}
        ])
        
        # ツール実行結果をモック
        agent.connection_manager.call_tool = AsyncMock(return_value={"result": 60})
        
        # タスク実行後のLLM判断をモック
        agent.llm_interface.judge_tool_execution_result = AsyncMock(return_value={
            "is_success": True, 
            "needs_retry": False, 
            "processed_result": "計算完了: 60",
            "summary": "計算が正常に完了しました"
        })
        
        await agent.process_request("30")
        
        # 履歴確認リクエスト - determine_execution_typeをモック
        agent.llm_interface.determine_execution_type = AsyncMock(return_value={
            "type": "NO_TOOL", 
            "response": "あなたの年齢は30歳です", 
            "reason": "履歴から確認"
        })
        
        result3 = await agent.process_request("私の年齢は？")
        
        # 年齢情報が正しく保持・参照される
        assert "30" in result3
        
        # 会話履歴に「30」の記録がある
        history = agent.state_manager.get_conversation_context(10)
        user_entries = [entry for entry in history if entry['role'] == 'user']
        assert any(entry['content'] == "30" for entry in user_entries)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])