#!/usr/bin/env python3
"""
Conversation Manager for MCP Agent
会話文脈と履歴の管理を専門に扱うモジュール

主な責任:
- 会話履歴の管理
- 文脈情報の取得と整形
- 実行結果の履歴管理
- LLM向けの文脈フォーマット
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from state_manager import StateManager
from config_manager import Config


class ConversationManager:
    """
    会話文脈と履歴を管理するクラス
    
    StateManagerと連携して永続化を行いながら、
    会話の文脈処理に特化した機能を提供
    """
    
    def __init__(self, state_manager: StateManager, config: Config):
        """
        Args:
            state_manager: 状態管理クラス（永続化を委譲）
            config: 設定辞書
        """
        self.state_manager = state_manager
        self.config = config
        self.conversation_history: List[Dict] = []
    
    def add_to_conversation(self, role: str, message: str, 
                           execution_results: Optional[List[Dict]] = None) -> None:
        """
        会話履歴に追加
        
        Args:
            role: ロール（user/assistant）
            message: メッセージ内容
            execution_results: 実行結果（オプション）
        """
        history_item = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message
        }
        
        # 実行結果があれば追加
        if execution_results:
            history_item["execution_results"] = execution_results
        
        self.conversation_history.append(history_item)
        
        # 履歴の長さ制限
        max_history = self.config.conversation.max_history
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
    
    def get_recent_context(self, max_items: Optional[int] = None, 
                          include_results: bool = True,
                          recent_tasks_only: bool = True) -> str:
        """
        最近の会話文脈を取得
        
        Args:
            max_items: 取得する会話数の上限
            include_results: 実行結果を含めるかどうか
            recent_tasks_only: 現在のクエリに関連するタスクのみを含めるか
            
        Returns:
            フォーマットされた文脈文字列
        """
        if max_items is None:
            max_items = self.config.conversation.context_limit
        
        # StateManagerから会話履歴を取得
        conversation_context = self.state_manager.get_conversation_context(max_items)
        
        if not conversation_context:
            return ""
        
        lines = []
        
        # 会話履歴をフォーマット
        for entry in conversation_context:
            role = "User" if entry['role'] == "user" else "Assistant"
            msg = entry['content'][:150] + "..." if len(entry['content']) > 150 else entry['content']
            timestamp = entry.get('timestamp', '')
            
            if timestamp:
                time_str = timestamp.split('T')[1][:5] if 'T' in timestamp else timestamp
                lines.append(f"[{time_str}] {role}: {msg}")
            else:
                lines.append(f"{role}: {msg}")
        
        # 実行結果を含める場合
        if include_results:
            lines.extend(self._format_execution_results(recent_tasks_only))
        
        return "\n".join(lines)
    
    def _format_execution_results(self, recent_tasks_only: bool) -> List[str]:
        """
        実行結果をフォーマット
        
        Args:
            recent_tasks_only: 最近のタスクのみを含めるか
            
        Returns:
            フォーマットされた実行結果の行リスト
        """
        lines = []
        completed_tasks = self.state_manager.get_completed_tasks()
        
        if recent_tasks_only:
            # 最近の3タスクのみ
            recent_tasks = completed_tasks[-3:] if completed_tasks else []
        else:
            recent_tasks = completed_tasks[-3:] if completed_tasks else []
        
        if recent_tasks:
            lines.append("\n## 直近の実行結果:")
            for i, task in enumerate(recent_tasks, 1):
                if task.result:
                    result_preview = str(task.result)[:300] + "..." if len(str(task.result)) > 300 else str(task.result)
                    lines.append(f"{i}. {task.tool} - {task.description}")
                    lines.append(f"   結果: {result_preview}")
        
        return lines
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        会話サマリーを取得
        
        Returns:
            会話の統計情報
        """
        user_messages = sum(1 for item in self.conversation_history if item["role"] == "user")
        assistant_messages = sum(1 for item in self.conversation_history if item["role"] == "assistant")
        execution_count = sum(1 for item in self.conversation_history if item.get("execution_results"))
        
        return {
            "total_messages": len(self.conversation_history),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "executions": execution_count,
            "history_size": len(self.conversation_history)
        }