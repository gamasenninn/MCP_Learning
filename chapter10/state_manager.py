#!/usr/bin/env python3
"""
State Manager for MCP Agent V6
状態管理システム - .mcp_agent/フォルダでテキストファイルベースの永続化

主要機能:
- 会話セッション管理
- タスク状態の永続化
- 人間向け可読ファイル形式
- セッション復元機能
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from utils import safe_str


@dataclass
class TaskState:
    """タスクの状態を表すクラス"""
    task_id: str
    tool: str
    params: Dict[str, Any]
    description: str
    status: str  # pending, executing, completed, failed, paused
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


@dataclass
class SessionState:
    """セッションの状態を表すクラス"""
    session_id: str
    created_at: str
    last_active: str
    conversation_context: List[Dict[str, str]]
    current_user_query: str = ""
    execution_type: str = ""  # NO_TOOL, SIMPLE, COMPLEX, CLARIFICATION
    pending_tasks: List[TaskState] = None
    completed_tasks: List[TaskState] = None
    
    def __post_init__(self):
        if self.pending_tasks is None:
            self.pending_tasks = []
        if self.completed_tasks is None:
            self.completed_tasks = []


class StateManager:
    """
    状態管理クラス
    
    .mcp_agent/フォルダ構造:
    - session.json: 現在のセッション情報
    - conversation.txt: 会話履歴（人間可読）
    - tasks/: タスク状態ファイル
      - pending.json: 実行待ちタスク
      - completed.json: 完了タスク
      - current.txt: 現在実行中タスクの詳細
    - history/: 過去のセッション履歴
    """
    
    def __init__(self, state_dir: str = ".mcp_agent"):
        self.state_dir = Path(state_dir)
        self.session_file = self.state_dir / "session.json"
        self.conversation_file = self.state_dir / "conversation.txt"
        self.tasks_dir = self.state_dir / "tasks"
        self.history_dir = self.state_dir / "history"
        
        # ディレクトリ構造を初期化
        self._ensure_directory_structure()
        
        self.current_session: Optional[SessionState] = None
    
    def _ensure_directory_structure(self):
        """必要なディレクトリ構造を作成"""
        for dir_path in [self.state_dir, self.tasks_dir, self.history_dir]:
            dir_path.mkdir(exist_ok=True)
    
    async def initialize_session(self, session_id: Optional[str] = None) -> str:
        """
        セッションを初期化
        
        Args:
            session_id: 既存セッションID（復元時）
            
        Returns:
            セッションID
        """
        if session_id and self._session_exists(session_id):
            # 既存セッションの復元
            return await self._restore_session(session_id)
        else:
            # 新しいセッションの作成
            return await self._create_new_session()
    
    def _session_exists(self, session_id: str) -> bool:
        """セッションが存在するかチェック"""
        return self.session_file.exists()
    
    async def _create_new_session(self) -> str:
        """新しいセッションを作成"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_session = SessionState(
            session_id=session_id,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat(),
            conversation_context=[]
        )
        
        await self._save_session()
        await self._write_conversation_log(f"=== 新しいセッション開始: {session_id} ===")
        
        return session_id
    
    async def _restore_session(self, session_id: str) -> str:
        """既存セッションを復元"""
        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # TaskStateオブジェクトを復元
            pending_tasks = [TaskState(**task) for task in session_data.get('pending_tasks', [])]
            completed_tasks = [TaskState(**task) for task in session_data.get('completed_tasks', [])]
            
            self.current_session = SessionState(
                session_id=session_data['session_id'],
                created_at=session_data['created_at'],
                last_active=datetime.now().isoformat(),
                conversation_context=session_data.get('conversation_context', []),
                current_user_query=session_data.get('current_user_query', ''),
                execution_type=session_data.get('execution_type', ''),
                pending_tasks=pending_tasks,
                completed_tasks=completed_tasks
            )
            
            await self._save_session()
            await self._write_conversation_log(f"=== セッション復元: {session_id} ===")
            
            return session_id
            
        except Exception as e:
            print(f"セッション復元エラー: {e}")
            return await self._create_new_session()
    
    async def _save_session(self):
        """セッション状態を保存"""
        if not self.current_session:
            return
        
        session_dict = asdict(self.current_session)
        session_dict['last_active'] = datetime.now().isoformat()
        
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(session_dict, f, ensure_ascii=False, indent=2)
    
    async def add_conversation_entry(self, role: str, content: str):
        """会話エントリを追加"""
        if not self.current_session:
            await self.initialize_session()
        
        entry = {
            "role": role,
            "content": safe_str(content),
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_session.conversation_context.append(entry)
        await self._save_session()
        await self._write_conversation_log(f"[{role.upper()}] {safe_str(content)}")
    
    async def _write_conversation_log(self, message: str):
        """会話ログをファイルに書き込み"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.conversation_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    async def set_user_query(self, query: str, execution_type: str):
        """ユーザークエリと実行タイプを設定"""
        if not self.current_session:
            await self.initialize_session()
        
        self.current_session.current_user_query = safe_str(query)
        self.current_session.execution_type = execution_type
        await self._save_session()
    
    async def add_pending_task(self, task: TaskState):
        """実行待ちタスクを追加"""
        if not self.current_session:
            await self.initialize_session()
        
        self.current_session.pending_tasks.append(task)
        await self._save_session()
        await self._save_task_status()
    
    async def move_task_to_completed(self, task_id: str, result: Any = None, error: str = None):
        """タスクを完了済みに移動"""
        if not self.current_session:
            return False
        
        # pending_tasksから該当タスクを探して削除
        task_to_complete = None
        for i, task in enumerate(self.current_session.pending_tasks):
            if task.task_id == task_id:
                task_to_complete = self.current_session.pending_tasks.pop(i)
                break
        
        if not task_to_complete:
            return False
        
        # タスクの状態を更新
        task_to_complete.status = "completed" if not error else "failed"
        task_to_complete.result = result
        task_to_complete.error = error
        task_to_complete.updated_at = datetime.now().isoformat()
        
        # completed_tasksに追加
        self.current_session.completed_tasks.append(task_to_complete)
        
        await self._save_session()
        await self._save_task_status()
        
        return True
    
    async def pause_all_tasks(self):
        """すべてのタスクを一時停止"""
        if not self.current_session:
            return
        
        for task in self.current_session.pending_tasks:
            if task.status == "executing":
                task.status = "paused"
                task.updated_at = datetime.now().isoformat()
        
        await self._save_session()
        await self._save_task_status()
    
    async def resume_paused_tasks(self):
        """一時停止したタスクを再開"""
        if not self.current_session:
            return
        
        for task in self.current_session.pending_tasks:
            if task.status == "paused":
                task.status = "pending"
                task.updated_at = datetime.now().isoformat()
        
        await self._save_session()
        await self._save_task_status()
    
    async def _save_task_status(self):
        """タスク状態を人間可読形式で保存"""
        if not self.current_session:
            return
        
        # pending.json
        pending_file = self.tasks_dir / "pending.json"
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(task) for task in self.current_session.pending_tasks], 
                     f, ensure_ascii=False, indent=2)
        
        # completed.json
        completed_file = self.tasks_dir / "completed.json"
        with open(completed_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(task) for task in self.current_session.completed_tasks], 
                     f, ensure_ascii=False, indent=2)
        
        # current.txt (現在の状況を人間可読形式で)
        current_file = self.tasks_dir / "current.txt"
        with open(current_file, 'w', encoding='utf-8') as f:
            f.write(f"現在のユーザー要求: {self.current_session.current_user_query}\n")
            f.write(f"実行タイプ: {self.current_session.execution_type}\n")
            f.write(f"実行待ちタスク数: {len(self.current_session.pending_tasks)}\n")
            f.write(f"完了済みタスク数: {len(self.current_session.completed_tasks)}\n\n")
            
            if self.current_session.pending_tasks:
                f.write("=== 実行待ちタスク ===\n")
                for i, task in enumerate(self.current_session.pending_tasks, 1):
                    f.write(f"{i}. [{task.status}] {task.description}\n")
                    f.write(f"   ツール: {task.tool}\n")
                    f.write(f"   作成: {task.created_at}\n\n")
    
    def get_conversation_context(self, max_entries: int = 10) -> List[Dict[str, str]]:
        """会話コンテキストを取得"""
        if not self.current_session:
            return []
        
        return self.current_session.conversation_context[-max_entries:]
    
    def get_pending_tasks(self) -> List[TaskState]:
        """実行待ちタスクを取得"""
        if not self.current_session:
            return []
        
        return self.current_session.pending_tasks.copy()
    
    def get_completed_tasks(self) -> List[TaskState]:
        """完了済みタスクを取得"""
        if not self.current_session:
            return []
        
        return self.current_session.completed_tasks.copy()
    
    def has_pending_tasks(self) -> bool:
        """実行待ちタスクがあるかチェック"""
        if not self.current_session:
            return False
        
        return len(self.current_session.pending_tasks) > 0
    
    async def archive_session(self):
        """現在のセッションをアーカイブ"""
        if not self.current_session:
            return
        
        # アーカイブファイル名
        archive_name = f"{self.current_session.session_id}.json"
        archive_path = self.history_dir / archive_name
        
        # セッション全体をアーカイブ
        archive_data = asdict(self.current_session)
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2)
        
        # 会話ログもアーカイブ
        if self.conversation_file.exists():
            conv_archive_path = self.history_dir / f"{self.current_session.session_id}_conversation.txt"
            with open(self.conversation_file, 'r', encoding='utf-8') as src:
                with open(conv_archive_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
    
    async def clear_current_session(self):
        """現在のセッションをクリア"""
        await self.archive_session()
        
        # ファイルを削除
        for file_path in [self.session_file, self.conversation_file]:
            if file_path.exists():
                file_path.unlink()
        
        # tasksディレクトリをクリア
        for task_file in self.tasks_dir.glob("*.json"):
            task_file.unlink()
        for task_file in self.tasks_dir.glob("*.txt"):
            task_file.unlink()
        
        self.current_session = None
    
    def get_session_summary(self) -> Dict[str, Any]:
        """現在のセッションの要約を取得"""
        if not self.current_session:
            return {"status": "no_session"}
        
        return {
            "session_id": self.current_session.session_id,
            "created_at": self.current_session.created_at,
            "last_active": self.current_session.last_active,
            "current_query": self.current_session.current_user_query,
            "execution_type": self.current_session.execution_type,
            "conversation_entries": len(self.current_session.conversation_context),
            "pending_tasks": len(self.current_session.pending_tasks),
            "completed_tasks": len(self.current_session.completed_tasks),
            "has_work_to_resume": len(self.current_session.pending_tasks) > 0
        }