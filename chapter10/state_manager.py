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
    execution_type: str = ""  # NO_TOOL, TOOL, CLARIFICATION
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
            self.logger.ulog(f"セッション復元エラー: {e}", "error:session")
            return await self._create_new_session()
    
    async def _save_session(self):
        """セッション状態を保存"""
        if not self.current_session:
            return
        
        session_dict = asdict(self.current_session)
        session_dict['last_active'] = datetime.now().isoformat()
        
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(session_dict, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
    
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
            f.flush()
            os.fsync(f.fileno())
    
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
            f.flush()
            os.fsync(f.fileno())
        
        # completed.json
        completed_file = self.tasks_dir / "completed.json"
        with open(completed_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(task) for task in self.current_session.completed_tasks], 
                     f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
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
            f.flush()
            os.fsync(f.fileno())
    
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
            f.flush()
            os.fsync(f.fileno())
        
        # 会話ログもアーカイブ
        if self.conversation_file.exists():
            conv_archive_path = self.history_dir / f"{self.current_session.session_id}_conversation.txt"
            with open(self.conversation_file, 'r', encoding='utf-8') as src:
                with open(conv_archive_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                    dst.flush()
                    os.fsync(dst.fileno())
    
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
    
    def get_session_status(self, task_manager=None, ui_mode: str = None, verbose: bool = None) -> Dict[str, Any]:
        """現在のセッション状態を取得（詳細版）"""
        session_summary = self.get_session_summary()
        
        # タスクサマリーを取得（task_managerが提供された場合）
        task_summary = {}
        if task_manager:
            task_summary = task_manager.get_task_summary()
        
        return {
            "session": session_summary,
            "tasks": task_summary,
            "can_resume": session_summary.get("has_work_to_resume", False),
            "ui_mode": ui_mode,
            "verbose": verbose
        }
    
    def export_session_data(self) -> Dict[str, Any]:
        """
        セッションデータをエクスポート用辞書として返す
        
        Returns:
            エクスポート用のセッション data辞書
        """
        from datetime import datetime
        
        # 会話履歴（全て）
        conversation_context = self.get_conversation_context(1000)
        
        # タスク履歴
        completed_tasks = self.get_completed_tasks()
        pending_tasks = self.get_pending_tasks()
        
        # セッション基本情報
        session_summary = self.get_session_summary()
        
        return {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "version": "1.0",
                "agent_version": "MCP Agent v6"
            },
            "session_info": {
                "session_id": self.current_session.session_id if self.current_session else None,
                "created_at": self.current_session.created_at if self.current_session else None,
                "conversation_entries": len(conversation_context),
                "execution_type": session_summary.get("execution_type"),
                "has_work_to_resume": session_summary.get("has_work_to_resume", False)
            },
            "conversation": conversation_context,
            "tasks": {
                "completed": [
                    {
                        "task_id": task.task_id,
                        "tool": task.tool,
                        "description": task.description,
                        "result": str(task.result) if task.result else None,
                        "error": task.error,
                        "created_at": task.created_at,
                        "updated_at": task.updated_at,
                        "status": task.status
                    }
                    for task in completed_tasks
                ],
                "pending": [
                    {
                        "task_id": task.task_id,
                        "tool": task.tool,
                        "description": task.description,
                        "params": task.params,
                        "created_at": task.created_at,
                        "status": task.status
                    }
                    for task in pending_tasks
                ]
            },
            "statistics": {
                "total_conversations": len(conversation_context),
                "total_tasks": len(completed_tasks) + len(pending_tasks),
                "completed_tasks": len(completed_tasks),
                "pending_tasks": len(pending_tasks)
            }
        }
    
    async def import_session_data(self, session_data: Dict[str, Any], clear_current: bool = True) -> bool:
        """
        セッションデータをインポートして復元
        
        Args:
            session_data: インポートするセッションデータ
            clear_current: 現在のセッションをクリアするかどうか
            
        Returns:
            成功フラグ
        """
        try:
            if clear_current:
                await self.clear_current_session()
                await self.initialize_session()
            
            # 会話履歴の復元
            conversation = session_data.get("conversation", [])
            for entry in conversation:
                await self.add_conversation_entry(entry["role"], entry["content"])
            
            # 完了タスクの復元
            completed_tasks = session_data.get("tasks", {}).get("completed", [])
            for task_data in completed_tasks:
                task = TaskState(
                    task_id=task_data["task_id"],
                    tool=task_data["tool"],
                    params={},  # 完了タスクはパラメータ不要
                    description=task_data["description"],
                    status="completed",
                    created_at=task_data.get("created_at"),
                    updated_at=task_data.get("updated_at"),
                    result=task_data.get("result"),
                    error=task_data.get("error")
                )
                self.completed_tasks.append(task)
            
            # 保留タスクの復元
            pending_tasks = session_data.get("tasks", {}).get("pending", [])
            for task_data in pending_tasks:
                task = TaskState(
                    task_id=task_data["task_id"],
                    tool=task_data["tool"],
                    params=task_data.get("params", {}),
                    description=task_data["description"],
                    status=task_data.get("status", "pending"),
                    created_at=task_data.get("created_at")
                )
                await self.add_pending_task(task)
            
            # セッション情報の更新
            if self.current_session and session_data.get("session_info"):
                session_info = session_data["session_info"]
                if session_info.get("execution_type"):
                    self.current_session.execution_type = session_info["execution_type"]
            
            # セッション状態を保存
            await self._save_session()
            
            return True
            
        except Exception as e:
            # エラーログ
            if hasattr(self, 'logger'):
                self.logger.ulog(f"セッションインポートエラー: {e}", "error")
            return False
    
    @staticmethod
    def list_saved_sessions(export_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        保存されたセッションファイルの一覧を取得
        
        Args:
            export_dir: エクスポートディレクトリパス（デフォルト: exports）
            
        Returns:
            セッションファイル情報のリスト
        """
        import json
        from pathlib import Path
        
        if export_dir is None:
            export_dir = Path.cwd() / "exports"
        else:
            export_dir = Path(export_dir)
        
        if not export_dir.exists():
            return []
        
        sessions = []
        for file_path in export_dir.glob("*.json"):
            try:
                # ファイルサイズと更新日時
                stat = file_path.stat()
                
                # JSONファイルの基本情報を読み取り
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                metadata = data.get("metadata", {})
                session_info = data.get("session_info", {})
                stats = data.get("statistics", {})
                
                sessions.append({
                    "filename": file_path.name,
                    "filepath": str(file_path),
                    "filesize": stat.st_size,
                    "modified": stat.st_mtime,
                    "exported_at": metadata.get("exported_at"),
                    "session_id": session_info.get("session_id"),
                    "conversations": stats.get("total_conversations", 0),
                    "tasks": stats.get("total_tasks", 0),
                    "version": metadata.get("version")
                })
                
            except (json.JSONDecodeError, KeyError, IOError):
                # 無効なJSONファイルは無視
                continue
        
        # 更新日時順でソート（新しい順）
        sessions.sort(key=lambda x: x["modified"], reverse=True)
        return sessions
    
    def get_export_dir(self) -> Path:
        """エクスポートディレクトリを取得・作成"""
        from pathlib import Path
        export_dir = Path(".mcp_agent/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir