#!/usr/bin/env python3
"""
REPL Commands for MCP Agent
対話型インターフェースのコマンド処理

主な機能:
- コマンド解析と実行
- エイリアス処理
- コマンド登録管理
"""

import asyncio
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass, field
from repl_command_handlers import ReplCommandHandlers


@dataclass
class Command:
    """コマンド定義"""
    name: str
    description: str
    handler: Callable
    aliases: List[str] = field(default_factory=list)
    usage: str = ""


class CommandManager:
    """REPLコマンド管理クラス"""
    
    def __init__(self, agent):
        """
        Args:
            agent: MCPAgentインスタンス
        """
        self.agent = agent
        self.commands: Dict[str, Command] = {}
        self.aliases: Dict[str, str] = {}
        self.handlers = ReplCommandHandlers(agent)
        self._register_commands()
    
    def _register_commands(self):
        """基本コマンドを登録"""
        # セッション管理コマンド
        self.register(
            name="/help",
            handler=self.handlers.cmd_help,
            description="利用可能なコマンド一覧を表示",
            aliases=["/?"],
            usage="/help [command]"
        )
        
        self.register(
            name="/status",
            handler=self.handlers.cmd_status,
            description="現在のセッション状態を表示",
            aliases=["/st", "/stat"],
            usage="/status"
        )
        
        self.register(
            name="/clear",
            handler=self.handlers.cmd_clear,
            description="現在のセッションをクリア",
            aliases=["/cls", "/reset"],
            usage="/clear"
        )
        
        # ツール・タスク管理コマンド
        self.register(
            name="/tools",
            handler=self.handlers.cmd_tools,
            description="利用可能なツール一覧を表示",
            aliases=["/t"],
            usage="/tools [-v|--verbose]"
        )
        
        self.register(
            name="/tasks",
            handler=self.handlers.cmd_tasks,
            description="タスク一覧を表示",
            aliases=["/task"],
            usage="/tasks [pending|completed|all]"
        )
        
        # 履歴・保存・読み込みコマンド
        self.register(
            name="/history",
            handler=self.handlers.cmd_history,
            description="会話履歴を表示",
            aliases=["/hist"],
            usage="/history [count]"
        )
        
        self.register(
            name="/save",
            handler=self.handlers.cmd_save,
            description="セッションをファイルに保存",
            aliases=["/export"],
            usage="/save [filename]"
        )
        
        self.register(
            name="/load",
            handler=self.handlers.cmd_load,
            description="保存されたセッションを読み込み",
            aliases=["/import"],
            usage="/load [filename|index]"
        )
        
        # 設定管理コマンド
        self.register(
            name="/config",
            handler=self.handlers.cmd_config,
            description="設定の表示と変更",
            aliases=["/cfg", "/set"],
            usage="/config [key] [value]"
        )
        
        self.register(
            name="/verbose",
            handler=self.handlers.cmd_verbose,
            description="詳細ログの切り替え",
            aliases=["/v"],
            usage="/verbose [on|off]"
        )
        
        self.register(
            name="/ui",
            handler=self.handlers.cmd_ui,
            description="UIモードの切り替え",
            aliases=["/display"],
            usage="/ui [basic|rich]"
        )
    
    def register(self, name: str, handler: Callable, description: str, 
                aliases: List[str] = None, usage: str = ""):
        """コマンドを登録"""
        command = Command(
            name=name,
            description=description,
            handler=handler,
            aliases=aliases or [],
            usage=usage or name
        )
        
        self.commands[name] = command
        
        # エイリアスを登録
        for alias in command.aliases:
            self.aliases[alias] = name
    
    async def process(self, user_input: str) -> Optional[str]:
        """
        コマンド処理のエントリーポイント
        
        Args:
            user_input: ユーザー入力文字列
            
        Returns:
            コマンド実行結果（コマンドでない場合はNone）
        """
        if not user_input.startswith("/"):
            return None
        
        # コマンドと引数を分離
        parts = user_input.split(" ", 1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # エイリアス解決
        if cmd_name in self.aliases:
            cmd_name = self.aliases[cmd_name]
        
        # コマンド実行
        if cmd_name in self.commands:
            try:
                command = self.commands[cmd_name]
                result = await command.handler(args.strip())
                return result
            except Exception as e:
                return f"コマンドエラー: {cmd_name}\nエラー: {str(e)}"
        else:
            return f"不明なコマンド: {cmd_name}\n'/help' でコマンド一覧を確認してください。"