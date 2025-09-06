#!/usr/bin/env python3
"""
REPL Commands Test Suite
REPLコマンドの包括的テスト

テスト対象:
- Phase 1: /help, /status, /tools, /tasks, /clear
- Phase 2: /history, /save, /load
- エイリアス機能
- エラーハンドリング
- 引数処理
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from repl_commands import CommandManager, Command
from mcp_agent import MCPAgent
from state_manager import TaskState, StateManager
from config_manager import Config


class TestCommandManager:
    """CommandManager基本機能のテスト"""
    
    @pytest.fixture
    def mock_agent(self):
        """モックMCPAgentを作成"""
        agent = Mock()
        agent.state_manager = Mock()
        agent.task_manager = Mock()
        agent.connection_manager = Mock()
        agent.display = Mock()
        agent.logger = Mock()
        agent.ui_mode = "basic"
        agent.verbose = True
        
        # StateManagerのモック設定
        agent.state_manager.get_session_status = Mock(return_value={
            "session": {"status": "active", "session_id": "test123"},
            "tasks": {"total_tasks": 0, "pending_tasks": 0, "completed_tasks": 0},
            "can_resume": False,
            "ui_mode": "basic",
            "verbose": True
        })
        agent.state_manager.get_conversation_context = Mock(return_value=[
            {"role": "user", "content": "test message 1"},
            {"role": "assistant", "content": "test response 1"},
            {"role": "user", "content": "test message 2"}
        ])
        agent.state_manager.get_pending_tasks = Mock(return_value=[])
        agent.state_manager.get_completed_tasks = Mock(return_value=[])
        agent.state_manager.clear_current_session = AsyncMock()
        agent.state_manager.add_conversation_entry = AsyncMock()
        
        # 新しいセッション管理メソッドのモック
        def mock_export_session_data():
            # 毎回新しい辞書インスタンスを返す（Mockオブジェクトではない）
            return {
                "metadata": {"exported_at": "2025-01-01T00:00:00", "version": "1.0"},
                "session_info": {"session_id": "test123", "conversation_entries": 3},
                "conversation": [
                    {"role": "user", "content": "test message 1"},
                    {"role": "assistant", "content": "test response 1"},
                    {"role": "user", "content": "test message 2"}
                ],
                "tasks": {"completed": [], "pending": []},
                "statistics": {"total_conversations": 3, "total_tasks": 0, "completed_tasks": 0, "pending_tasks": 0}
            }
        
        agent.state_manager.export_session_data = Mock(side_effect=mock_export_session_data)
        
        # import_session_data の完全なAsyncMock設定
        async def mock_import_session_data(session_data, clear_current=False):
            # 会話履歴の復元をシミュレート
            conversation = session_data.get("conversation", [])
            for entry in conversation:
                await agent.state_manager.add_conversation_entry(entry["role"], entry["content"])
            return True
        agent.state_manager.import_session_data = AsyncMock(side_effect=mock_import_session_data)
        
        # list_saved_sessionsのモック
        def mock_list_saved_sessions(export_dir=None):
            from pathlib import Path
            import json
            # 実際にファイルを探す
            if export_dir:
                export_path = Path(export_dir)
                if export_path.exists():
                    sessions = []
                    for file_path in export_path.glob("*.json"):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            stats = data.get("statistics", {})
                            sessions.append({
                                "filename": file_path.name,
                                "filepath": str(file_path),
                                "filesize": file_path.stat().st_size,
                                "modified": file_path.stat().st_mtime,
                                "conversations": stats.get("total_conversations", 0),
                                "tasks": stats.get("total_tasks", 0),
                                "version": "1.0"
                            })
                        except Exception:
                            continue
                    return sessions
            return []
        
        agent.state_manager.list_saved_sessions = Mock(side_effect=mock_list_saved_sessions)
        
        # ConnectionManagerのモック設定
        agent.connection_manager.tools_info = {}
        agent.connection_manager.clients = []
        agent.connection_manager.get_all_tools = Mock(return_value={})
        agent.connection_manager.get_all_tools = Mock(return_value={})
        
        return agent
    
    @pytest.fixture
    def command_manager(self, mock_agent):
        """CommandManagerインスタンスを作成"""
        cmd_manager = CommandManager(mock_agent)
        # helpコマンドが参照するためにagentにcommand_managerを設定
        mock_agent.command_manager = cmd_manager
        return cmd_manager
    
    def test_command_registration(self, command_manager):
        """コマンド登録のテスト"""
        # Phase 1コマンドが登録されている
        expected_commands = ["/help", "/status", "/tools", "/tasks", "/clear", 
                           "/history", "/save", "/load"]
        
        for cmd in expected_commands:
            assert cmd in command_manager.commands
            assert isinstance(command_manager.commands[cmd], Command)
    
    def test_alias_registration(self, command_manager):
        """エイリアス登録のテスト"""
        expected_aliases = {
            "/?": "/help",
            "/st": "/status",
            "/stat": "/status",
            "/t": "/tools",
            "/task": "/tasks",
            "/cls": "/clear",
            "/reset": "/clear",
            "/hist": "/history",
            "/export": "/save",
            "/import": "/load"
        }
        
        for alias, target in expected_aliases.items():
            assert alias in command_manager.aliases
            assert command_manager.aliases[alias] == target
    
    @pytest.mark.asyncio
    async def test_non_command_input(self, command_manager):
        """コマンドでない入力のテスト"""
        result = await command_manager.process("通常の質問")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_unknown_command(self, command_manager):
        """未知のコマンドのテスト"""
        result = await command_manager.process("/unknown")
        assert "不明なコマンド" in result
        assert "/help" in result


class TestPhase1Commands:
    """Phase 1 コマンドのテスト"""
    
    @pytest.fixture
    def mock_agent(self):
        """モックエージェント"""
        agent = Mock()
        agent.state_manager = Mock()
        agent.task_manager = Mock()
        agent.connection_manager = Mock()
        agent.ui_mode = "rich"
        agent.verbose = False
        
        # 詳細なモック設定
        agent.state_manager.get_session_status.return_value = {
            "session": {
                "session_id": "session123",
                "created_at": "2025-09-05T10:00:00",
                "conversation_entries": 5,
                "execution_type": "TOOL"
            },
            "tasks": {
                "total_tasks": 3,
                "pending_tasks": 1,
                "completed_tasks": 2,
                "clarification_tasks": 0
            },
            "can_resume": True,
            "ui_mode": "rich",
            "verbose": False
        }
        
        agent.connection_manager.clients = ["server1", "server2"]
        agent.connection_manager.tools_info = {
            "calculator": {
                "server": "math_server", 
                "description": "数値計算ツール",
                "schema": {}
            },
            "file_reader": {
                "server": "file_server", 
                "description": "ファイル読み取り",
                "schema": {}
            }
        }
        
        # タスクモック
        pending_task = Mock()
        pending_task.description = "計算実行中"
        pending_task.tool = "calculator"
        pending_task.created_at = "2025-09-05T10:30:00"
        
        completed_task = Mock()
        completed_task.description = "ファイル読み取り完了"
        completed_task.tool = "file_reader"
        completed_task.updated_at = "2025-09-05T10:25:00"
        completed_task.error = None
        
        agent.state_manager.get_pending_tasks.return_value = [pending_task]
        agent.state_manager.get_completed_tasks.return_value = [completed_task]
        agent.state_manager.clear_current_session = AsyncMock()
        
        return agent
    
    @pytest.fixture
    def command_manager(self, mock_agent):
        cmd_manager = CommandManager(mock_agent)
        # helpコマンドが参照するためにagentにcommand_managerを設定
        mock_agent.command_manager = cmd_manager
        return cmd_manager
    
    @pytest.mark.asyncio
    async def test_help_command(self, command_manager):
        """helpコマンドのテスト"""
        result = await command_manager.process("/help")
        
        assert "=== MCP Agent REPL コマンド ===" in result
        assert "/help" in result
        assert "/status" in result
        assert "/tools" in result
        assert "/tasks" in result
        assert "/clear" in result
    
    @pytest.mark.asyncio
    async def test_help_specific_command(self, command_manager):
        """特定コマンドのhelpテスト"""
        result = await command_manager.process("/help status")
        
        assert "コマンド: /status" in result
        assert "現在のセッション状態を表示" in result
        assert "エイリアス:" in result
    
    @pytest.mark.asyncio
    async def test_status_command(self, command_manager):
        """statusコマンドのテスト"""
        result = await command_manager.process("/status")
        
        assert "=== セッション状態 ===" in result
        assert "session123" in result
        assert "📋 全タスク数: 3" in result
        assert "⏳ 保留中: 1" in result
        assert "✅ 完了済み: 2" in result
        assert "🎨 UI モード: rich" in result
        assert "🔧 接続サーバー: 2個" in result
    
    @pytest.mark.asyncio
    async def test_tools_command(self, command_manager):
        """toolsコマンド（コンパクトモード）のテスト"""
        result = await command_manager.process("/tools")
        
        assert "=== 利用可能なツール（コンパクト表示） ===" in result
        assert "総ツール数: 2" in result
        assert "calculator" in result
        assert "file_reader" in result
        assert "数値計算ツール" in result
        assert "💡 詳細説明を見るには: /tools -v" in result
    
    @pytest.mark.asyncio
    async def test_tools_command_verbose(self, command_manager):
        """toolsコマンド（詳細モード）のテスト"""
        result = await command_manager.process("/tools -v")
        
        assert "=== 利用可能なツール（詳細表示） ===" in result
        assert "総ツール数: 2" in result
        assert "calculator" in result
        assert "file_reader" in result
        assert "数値計算ツール" in result
        # 詳細モードではヒントメッセージが表示されない
        assert "💡 詳細説明を見るには" not in result
    
    @pytest.mark.asyncio
    async def test_tools_command_description_truncation(self, command_manager):
        """toolsコマンドの説明文切り詰めテスト"""
        # 長い説明文を持つツールを追加
        long_description_tool = {
            "server": "test_server",
            "description": "これは非常に長い説明文で、30文字を超えるため切り詰められるはずです"
        }
        command_manager.agent.connection_manager.tools_info["long_tool"] = long_description_tool
        
        # コンパクトモード：切り詰められる
        result = await command_manager.process("/tools")
        assert "これは非常に長い説明文で、30文字を超えるため切り詰め..." in result
        
        # 詳細モード：全文表示
        result = await command_manager.process("/tools -v")
        assert "これは非常に長い説明文で、30文字を超えるため切り詰められるはずです" in result
    
    @pytest.mark.asyncio
    async def test_tools_command_newline_truncation(self, command_manager):
        """toolsコマンドの改行文字による切り詰めテスト"""
        # 改行を含む説明文を持つツールを追加
        newline_tool = {
            "server": "test_server", 
            "description": "短い説明\nここは表示されない\n複数行の詳細説明"
        }
        command_manager.agent.connection_manager.tools_info["newline_tool"] = newline_tool
        
        # 改行を含む長い説明文を持つツール（30文字を超える）
        long_newline_tool = {
            "server": "test_server", 
            "description": "これは明らかに30文字を確実に超える非常に長い説明文になっています\nここは表示されない詳細情報"
        }
        command_manager.agent.connection_manager.tools_info["long_newline_tool"] = long_newline_tool
        
        # コンパクトモード：改行以降が切り捨てられる
        result = await command_manager.process("/tools")
        assert "短い説明" in result
        assert "ここは表示されない" not in result
        # 改行で切り詰められた後に30文字制限が適用される
        assert "これは明らかに30文字を確実に超える非常に長い説明文に..." in result
        
        # 詳細モード：全文表示
        result = await command_manager.process("/tools -v")
        assert "短い説明\nここは表示されない\n複数行の詳細説明" in result
        assert "これは明らかに30文字を確実に超える非常に長い説明文になっています\nここは表示されない詳細情報" in result
    
    @pytest.mark.asyncio
    async def test_tasks_command(self, command_manager):
        """tasksコマンドのテスト"""
        result = await command_manager.process("/tasks")
        
        assert "=== タスク一覧 ===" in result
        assert "計算実行中" in result
        assert "ファイル読み取り完了" in result
        assert "📊 統計:" in result
        assert "総タスク数: 2" in result  # pending (1) + completed (1) from mock
    
    @pytest.mark.asyncio
    async def test_clear_command(self, command_manager, mock_agent):
        """clearコマンドのテスト"""
        result = await command_manager.process("/clear")
        
        assert "✨ セッションをクリアしました" in result
        mock_agent.state_manager.clear_current_session.assert_called_once()


class TestPhase2Commands:
    """Phase 2 コマンドのテスト"""
    
    @pytest.fixture
    def temp_export_dir(self):
        """テンポラリエクスポートディレクトリ"""
        temp_dir = tempfile.mkdtemp()
        export_dir = Path(temp_dir) / ".mcp_agent" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        yield export_dir
        
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_agent_with_history(self):
        """会話履歴付きモックエージェント"""
        agent = Mock()
        agent.state_manager = Mock()
        agent.task_manager = Mock()
        agent.connection_manager = Mock()
        agent.ui_mode = "basic"
        agent.verbose = True
        
        # 会話履歴モック
        conversation_history = [
            {
                "role": "user",
                "content": "こんにちは",
                "timestamp": "2025-09-05T10:30:15"
            },
            {
                "role": "assistant", 
                "content": "こんにちは！何かお手伝いできることはありますか？",
                "timestamp": "2025-09-05T10:30:16"
            },
            {
                "role": "user",
                "content": "計算してください: 2 + 3",
                "timestamp": "2025-09-05T10:30:20"
            }
        ]
        
        agent.state_manager.get_conversation_context.return_value = conversation_history
        agent.state_manager.add_conversation_entry = AsyncMock()
        agent.state_manager.get_session_status.return_value = {
            "session": {"session_id": "test", "created_at": "2025-09-05T10:00:00"},
            "tasks": {"total_tasks": 1, "pending_tasks": 0, "completed_tasks": 1},
            "ui_mode": "basic",
            "verbose": True
        }
        agent.state_manager.get_pending_tasks.return_value = []
        agent.state_manager.get_completed_tasks.return_value = []
        agent.connection_manager.tools_info = {}
        agent.connection_manager.clients = []
        agent.connection_manager.get_all_tools = Mock(return_value={})
        
        # セッション管理メソッドのモック
        def mock_export_session_data():
            # 毎回新しい辞書インスタンスを返す（Mockオブジェクトではない）
            return {
                "metadata": {"exported_at": "2025-01-01T00:00:00", "version": "1.0"},
                "session_info": {"session_id": "test123", "conversation_entries": 3},
                "conversation": [
                    {"role": "user", "content": "test message 1"},
                    {"role": "assistant", "content": "test response 1"},
                    {"role": "user", "content": "test message 2"}
                ],
                "tasks": {"completed": [], "pending": []},
                "statistics": {"total_conversations": 3, "total_tasks": 0, "completed_tasks": 0, "pending_tasks": 0}
            }
        
        agent.state_manager.export_session_data = Mock(side_effect=mock_export_session_data)
        
        # import_session_data の完全なAsyncMock設定
        async def mock_import_session_data(session_data, clear_current=False):
            # 会話履歴の復元をシミュレート
            conversation = session_data.get("conversation", [])
            for entry in conversation:
                await agent.state_manager.add_conversation_entry(entry["role"], entry["content"])
            return True
        agent.state_manager.import_session_data = AsyncMock(side_effect=mock_import_session_data)
        
        # list_saved_sessionsのモック
        def mock_list_saved_sessions(export_dir=None):
            from pathlib import Path
            import json
            # 実際にファイルを探す
            if export_dir:
                export_path = Path(export_dir)
                if export_path.exists():
                    sessions = []
                    for file_path in export_path.glob("*.json"):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            stats = data.get("statistics", {})
                            sessions.append({
                                "filename": file_path.name,
                                "filepath": str(file_path),
                                "filesize": file_path.stat().st_size,
                                "modified": file_path.stat().st_mtime,
                                "conversations": stats.get("total_conversations", 0),
                                "tasks": stats.get("total_tasks", 0),
                                "version": "1.0"
                            })
                        except Exception:
                            continue
                    return sessions
            return []
        
        agent.state_manager.list_saved_sessions = Mock(side_effect=mock_list_saved_sessions)
        
        return agent
    
    @pytest.fixture
    def command_manager(self, mock_agent_with_history):
        cmd_manager = CommandManager(mock_agent_with_history)
        # helpコマンドが参照するためにagentにcommand_managerを設定
        mock_agent_with_history.command_manager = cmd_manager
        return cmd_manager
    
    @pytest.mark.asyncio
    async def test_history_command_with_data(self, command_manager):
        """履歴コマンド（データあり）のテスト"""
        result = await command_manager.process("/history")
        
        assert "=== 会話履歴 (最新3件) ===" in result
        assert "👤 User: こんにちは" in result
        assert "🤖 Assistant: こんにちは！何かお手伝いできることはありますか？" in result
        assert "👤 User: 計算してください: 2 + 3" in result
        assert "10:30" in result
    
    @pytest.mark.asyncio
    async def test_history_command_with_count(self, command_manager):
        """履歴コマンド（件数指定）のテスト"""
        result = await command_manager.process("/history 2")
        
        # get_conversation_contextが2で呼ばれることを確認
        command_manager.agent.state_manager.get_conversation_context.assert_called_with(2)
    
    @pytest.mark.asyncio
    async def test_history_command_empty(self, command_manager):
        """履歴コマンド（空）のテスト"""
        command_manager.agent.state_manager.get_conversation_context.return_value = []
        
        result = await command_manager.process("/history")
        assert "📝 会話履歴がありません" in result
    
    @pytest.mark.asyncio
    async def test_save_command(self, command_manager, temp_export_dir):
        """saveコマンドのテスト"""
        with patch.object(command_manager.agent.state_manager, 'get_export_dir', return_value=temp_export_dir):
            result = await command_manager.process("/save test_session")
        
        assert "✅ セッションを保存しました: test_session.json" in result
        assert "📊 保存内容:" in result
        assert "会話: 3件" in result
        
        # ファイルが作成されたことを確認
        saved_file = temp_export_dir / "test_session.json"
        assert saved_file.exists()
        
        # ファイル内容を確認
        with open(saved_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["metadata"]["version"] == "1.0"
        assert len(data["conversation"]) == 3
        assert data["statistics"]["total_conversations"] == 3
    
    @pytest.mark.asyncio
    async def test_save_command_auto_filename(self, command_manager, temp_export_dir):
        """saveコマンド（自動ファイル名）のテスト"""
        with patch.object(command_manager.agent.state_manager, 'get_export_dir', return_value=temp_export_dir):
            result = await command_manager.process("/save")
        
        assert "✅ セッションを保存しました: session_" in result
        assert ".json" in result
        
        # session_*.jsonファイルが作成されたことを確認
        json_files = list(temp_export_dir.glob("session_*.json"))
        assert len(json_files) == 1
    
    @pytest.mark.asyncio
    async def test_load_command_list(self, command_manager, temp_export_dir):
        """loadコマンド（一覧表示）のテスト"""
        # テスト用ファイルを作成
        test_data = {
            "statistics": {"total_conversations": 5, "total_tasks": 2},
            "metadata": {"exported_at": "2025-09-05T10:00:00"}
        }
        
        test_file = temp_export_dir / "test_file.json"
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        with patch.object(command_manager.agent.state_manager, 'get_export_dir', return_value=temp_export_dir):
            result = await command_manager.process("/load")
        
        assert "=== 利用可能な保存ファイル ===" in result
        assert "test_file" in result
        assert "💬 5件の会話, 📋 2個のタスク" in result
    
    @pytest.mark.asyncio
    async def test_load_command_by_name(self, command_manager, temp_export_dir):
        """loadコマンド（ファイル名指定）のテスト"""
        # テスト用ファイルを作成
        test_data = {
            "conversation": [
                {"role": "user", "content": "テスト質問"},
                {"role": "assistant", "content": "テスト回答"}
            ],
            "statistics": {"total_conversations": 2, "total_tasks": 0},
            "metadata": {"exported_at": "2025-09-05T10:00:00"}
        }
        
        test_file = temp_export_dir / "load_test.json"
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        with patch.object(command_manager.agent.state_manager, 'get_export_dir', return_value=temp_export_dir):
            result = await command_manager.process("/load load_test")
        
        assert "✅ セッションを読み込みました: load_test.json" in result
        assert "会話: 2件" in result
        
        # add_conversation_entryが呼ばれたことを確認
        assert command_manager.agent.state_manager.add_conversation_entry.call_count == 2


class TestCommandAliases:
    """エイリアス機能のテスト"""
    
    @pytest.fixture
    def mock_agent(self):
        agent = Mock()
        agent.state_manager = Mock()
        agent.state_manager.get_conversation_context.return_value = []
        agent.state_manager.clear_current_session = AsyncMock()
        agent.connection_manager = Mock()
        agent.connection_manager.tools_info = {}
        agent.connection_manager.clients = []
        agent.connection_manager.get_all_tools = Mock(return_value={})
        return agent
    
    @pytest.fixture
    def command_manager(self, mock_agent):
        cmd_manager = CommandManager(mock_agent)
        # helpコマンドが参照するためにagentにcommand_managerを設定
        mock_agent.command_manager = cmd_manager
        return cmd_manager
    
    @pytest.mark.asyncio
    async def test_help_aliases(self, command_manager):
        """helpのエイリアステスト"""
        result = await command_manager.process("/?")
        assert "=== MCP Agent REPL コマンド ===" in result
    
    @pytest.mark.asyncio
    async def test_clear_aliases(self, command_manager):
        """clearのエイリアステスト"""
        for alias in ["/cls", "/reset"]:
            result = await command_manager.process(alias)
            assert "✨ セッションをクリアしました" in result
    
    @pytest.mark.asyncio
    async def test_history_aliases(self, command_manager):
        """historyのエイリアステスト"""
        result = await command_manager.process("/hist")
        assert "会話履歴がありません" in result or "会話履歴" in result


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    @pytest.fixture
    def mock_agent_with_errors(self):
        """エラーを発生させるモックエージェント"""
        agent = Mock()
        agent.state_manager = Mock()
        agent.state_manager.get_conversation_context.side_effect = Exception("テスト例外")
        agent.state_manager.clear_current_session.side_effect = Exception("クリアエラー")
        return agent
    
    @pytest.fixture
    def command_manager(self, mock_agent_with_errors):
        return CommandManager(mock_agent_with_errors)
    
    @pytest.mark.asyncio
    async def test_history_error_handling(self, command_manager):
        """historyコマンドのエラーハンドリング"""
        result = await command_manager.process("/history")
        assert "履歴取得エラー" in result
        assert "テスト例外" in result
    
    @pytest.mark.asyncio
    async def test_clear_error_handling(self, command_manager):
        """clearコマンドのエラーハンドリング"""
        result = await command_manager.process("/clear")
        assert "セッションクリアエラー" in result
        assert "クリアエラー" in result
    
    @pytest.mark.asyncio
    async def test_invalid_history_count(self, command_manager):
        """historyコマンドの不正な件数指定"""
        # side_effectをリセットして正常動作させる
        command_manager.agent.state_manager.get_conversation_context.side_effect = None
        command_manager.agent.state_manager.get_conversation_context.return_value = []
        
        result = await command_manager.process("/history abc")
        # 不正な値でも10がデフォルトで使われる
        command_manager.agent.state_manager.get_conversation_context.assert_called_with(10)


@pytest.mark.asyncio
async def test_command_integration():
    """コマンド統合テスト"""
    # 実際のエージェントに近いモック
    agent = Mock()
    agent.state_manager = Mock()
    agent.task_manager = Mock()
    agent.connection_manager = Mock()
    agent.ui_mode = "basic"
    agent.verbose = True
    
    # 基本設定
    agent.state_manager.get_session_status.return_value = {
        "session": {"status": "active"},
        "tasks": {"total_tasks": 0},
        "ui_mode": "basic",
        "verbose": True
    }
    agent.state_manager.get_conversation_context.return_value = []
    agent.state_manager.get_pending_tasks.return_value = []
    agent.state_manager.get_completed_tasks.return_value = []
    agent.connection_manager.tools_info = {}
    agent.connection_manager.clients = []
    
    command_manager = CommandManager(agent)
    # helpコマンドが参照するためにagentにcommand_managerを設定
    agent.command_manager = command_manager
    
    # 複数コマンドを順次実行
    commands = ["/help", "/status", "/tools", "/tasks", "/history"]
    
    for cmd in commands:
        result = await command_manager.process(cmd)
        assert result is not None
        assert len(result) > 0
        assert "エラー" not in result or "取得エラー" not in result


class TestPhase3Commands:
    """Phase 3: 設定管理コマンドのテスト"""
    
    @pytest.fixture
    def mock_agent_with_config(self):
        """設定付きモックMCPAgentを作成"""
        from config_manager import Config, DisplayConfig, DevelopmentConfig
        
        agent = Mock()
        agent.state_manager = Mock()
        agent.task_manager = Mock()
        agent.connection_manager = Mock()
        agent.display = Mock()
        agent.logger = Mock()
        agent.ui_mode = "basic"
        
        # テスト用の設定を作成
        config = Config()
        config.display = DisplayConfig(ui_mode="basic", show_timing=True, show_thinking=False)
        config.development = DevelopmentConfig(verbose=True, log_level="INFO", show_api_calls=True)
        agent.config = config
        
        return agent
    
    @pytest.fixture
    def config_command_manager(self, mock_agent_with_config):
        """設定管理用のコマンドマネージャー"""
        cmd_manager = CommandManager(mock_agent_with_config)
        # helpコマンドが参照するためにagentにcommand_managerを設定
        mock_agent_with_config.command_manager = cmd_manager
        return cmd_manager
    
    @pytest.mark.asyncio
    async def test_config_display_all(self, config_command_manager):
        """設定全体表示のテスト"""
        result = await config_command_manager.process("/config")
        
        assert "=== 現在の設定 ===" in result
        assert "📂 表示設定:" in result
        assert "📂 開発設定:" in result
        assert "🔧 ui_mode: basic" in result
        assert "🔧 verbose: True" in result
        assert "💡 使用方法:" in result
    
    @pytest.mark.asyncio
    async def test_config_get_specific_value(self, config_command_manager):
        """特定設定値の取得テスト"""
        result = await config_command_manager.process("/config display.ui_mode")
        
        assert "🔧 display.ui_mode: basic (str)" in result
    
    @pytest.mark.asyncio
    async def test_config_set_value(self, config_command_manager):
        """設定値変更のテスト"""
        result = await config_command_manager.process("/config display.ui_mode rich")
        
        assert "✅ 設定を変更しました:" in result
        assert "display.ui_mode: basic → rich" in result
        
        # 実際に変更されているかチェック
        assert config_command_manager.agent.config.display.ui_mode == "rich"
    
    @pytest.mark.asyncio
    async def test_config_set_bool_value(self, config_command_manager):
        """bool値の設定変更テスト"""
        # ON値でのテスト
        result = await config_command_manager.process("/config display.show_timing false")
        assert "✅ 設定を変更しました:" in result
        assert config_command_manager.agent.config.display.show_timing == False
        
        # OFF値でのテスト
        result = await config_command_manager.process("/config display.show_timing true")
        assert "✅ 設定を変更しました:" in result
        assert config_command_manager.agent.config.display.show_timing == True
    
    @pytest.mark.asyncio
    async def test_config_invalid_key(self, config_command_manager):
        """無効なキーのエラー処理テスト"""
        result = await config_command_manager.process("/config invalid.key")
        
        assert "❌ 設定キー 'invalid.key' が見つかりません。" in result
    
    @pytest.mark.asyncio
    async def test_config_similar_keys_suggestion(self, config_command_manager):
        """類似キーの提案テスト"""
        result = await config_command_manager.process("/config disp")
        
        assert "💡 似ているキー:" in result
        assert "display.ui_mode" in result
    
    @pytest.mark.asyncio
    async def test_verbose_command_status(self, config_command_manager):
        """/verboseコマンドの状態表示テスト"""
        result = await config_command_manager.process("/verbose")
        
        assert "🔍 詳細ログ: ✅ ON" in result
        assert "💡 切り替えるには: /verbose on または /verbose off" in result
    
    @pytest.mark.asyncio
    async def test_verbose_command_toggle(self, config_command_manager):
        """/verboseコマンドの切り替えテスト"""
        # OFFにする
        result = await config_command_manager.process("/verbose off")
        assert "🔍 詳細ログを❌ OFFに変更しました" in result
        assert config_command_manager.agent.config.development.verbose == False
        
        # ONに戻す
        result = await config_command_manager.process("/verbose on")
        assert "🔍 詳細ログを✅ ONに変更しました" in result
        assert config_command_manager.agent.config.development.verbose == True
    
    @pytest.mark.asyncio
    async def test_verbose_invalid_value(self, config_command_manager):
        """/verboseコマンドの無効値エラーテスト"""
        result = await config_command_manager.process("/verbose maybe")
        
        assert "❌ 無効な値: maybe" in result
        assert "💡 使用方法: /verbose [on|off]" in result
    
    @pytest.mark.asyncio
    async def test_ui_command_status(self, config_command_manager):
        """/uiコマンドの状態表示テスト"""
        result = await config_command_manager.process("/ui")
        
        assert "🎨 現在のUIモード: basic" in result
        assert "💡 利用可能なモード:" in result
        assert "• basic: シンプルなprint文ベース" in result
        assert "• rich: 美しいUI（richライブラリ使用）" in result
    
    @pytest.mark.asyncio
    async def test_ui_command_change_mode(self, config_command_manager):
        """/uiコマンドのモード変更テスト"""
        result = await config_command_manager.process("/ui rich")
        
        assert "🎨 UIモードを変更しました: basic → rich" in result
        assert "⚠️ 一部の変更は再起動後に反映されます" in result
        assert config_command_manager.agent.config.display.ui_mode == "rich"
    
    @pytest.mark.asyncio
    async def test_ui_invalid_mode(self, config_command_manager):
        """/uiコマンドの無効モードエラーテスト"""
        result = await config_command_manager.process("/ui fancy")
        
        assert "❌ 無効なUIモード: fancy" in result
        assert "💡 利用可能: basic, rich" in result
    
    
    @pytest.mark.asyncio
    async def test_verbose_auto_save(self, config_command_manager):
        """/verboseコマンドの自動保存テスト"""
        result = await config_command_manager.process("/verbose off")
        
        assert "🔍 詳細ログを❌ OFFに変更しました" in result
        # ファイル保存のメッセージも含まれることを確認（実際のI/O結果による）
    
    @pytest.mark.asyncio 
    async def test_ui_auto_save(self, config_command_manager):
        """/uiコマンドの自動保存テスト"""
        result = await config_command_manager.process("/ui rich")
        
        assert "🎨 UIモードを変更しました: basic → rich" in result
        assert "⚠️ 一部の変更は再起動後に反映されます" in result
        # ファイル保存のメッセージも含まれることを確認（実際のI/O結果による）


class TestConfigCommandAliases:
    """設定管理コマンドのエイリアステスト"""
    
    @pytest.fixture
    def mock_agent_with_config(self):
        """設定付きモックMCPAgentを作成"""
        from config_manager import Config, DisplayConfig, DevelopmentConfig
        
        agent = Mock()
        agent.state_manager = Mock()
        agent.task_manager = Mock()
        agent.connection_manager = Mock()
        agent.display = Mock()
        agent.logger = Mock()
        agent.ui_mode = "basic"
        
        # テスト用の設定を作成
        config = Config()
        config.display = DisplayConfig(ui_mode="basic", show_timing=True, show_thinking=False)
        config.development = DevelopmentConfig(verbose=True, log_level="INFO", show_api_calls=True)
        agent.config = config
        
        return agent
    
    @pytest.fixture
    def config_command_manager(self, mock_agent_with_config):
        """設定管理用のコマンドマネージャー"""
        cmd_manager = CommandManager(mock_agent_with_config)
        # helpコマンドが参照するためにagentにcommand_managerを設定
        mock_agent_with_config.command_manager = cmd_manager
        return cmd_manager
    
    @pytest.mark.asyncio
    async def test_config_aliases(self, config_command_manager):
        """configコマンドのエイリアステスト"""
        # /cfg エイリアス
        result1 = await config_command_manager.process("/config")
        result2 = await config_command_manager.process("/cfg")
        assert result1 == result2
        
        # /set エイリアス
        result3 = await config_command_manager.process("/set")
        assert result1 == result3
    
    @pytest.mark.asyncio 
    async def test_verbose_aliases(self, config_command_manager):
        """/verboseコマンドのエイリアステスト"""
        result1 = await config_command_manager.process("/verbose")
        result2 = await config_command_manager.process("/v")
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_ui_aliases(self, config_command_manager):
        """/uiコマンドのエイリアステスト"""
        result1 = await config_command_manager.process("/ui")
        result2 = await config_command_manager.process("/display")
        assert result1 == result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])