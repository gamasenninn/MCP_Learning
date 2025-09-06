#!/usr/bin/env python3
"""
Clarification Handler for MCP Agent
CLARIFICATION機能の統合処理クラス

このクラスはMCPAgentとTaskManagerからCLARIFICATION関連機能を分離し、
単一責任原則に基づいた明確な責任分離を実現します。

主要機能:
- CLARIFICATION判定と処理
- ユーザー確認フローの管理
- skipコマンドの処理
- 会話履歴との統合
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from state_manager import StateManager, TaskState
from task_manager import TaskManager, ClarificationRequest
from conversation_manager import ConversationManager
from llm_interface import LLMInterface
from utils import Logger


class ClarificationHandler:
    """CLARIFICATION機能の統合ハンドラー"""
    
    def __init__(self, 
                 state_manager: StateManager,
                 task_manager: TaskManager,
                 conversation_manager: ConversationManager,
                 llm_interface: LLMInterface,
                 logger: Logger):
        """
        初期化
        
        Args:
            state_manager: 状態管理インスタンス
            task_manager: タスク管理インスタンス
            conversation_manager: 会話管理インスタンス
            llm_interface: LLM通信インスタンス
            logger: ロガーインスタンス
        """
        self.state_manager = state_manager
        self.task_manager = task_manager
        self.conversation_manager = conversation_manager
        self.llm_interface = llm_interface
        self.logger = logger
    
    async def handle_clarification_needed(self, user_query: str, execution_result: Dict) -> str:
        """
        CLARIFICATION必要時の処理
        
        Args:
            user_query: ユーザークエリ
            execution_result: 実行判定結果（CLARIFICATION情報含む）
            
        Returns:
            ユーザーへの確認メッセージ
        """
        clarification_info = execution_result.get('clarification', {})
        
        # CLARIFICATIONタスクを生成
        clarification_task = TaskState(
            task_id=f"clarification_{int(time.time())}",
            tool="CLARIFICATION",
            params={
                "question": clarification_info.get('question', '詳細情報をお教えください'),
                "context": f"要求: {user_query}",
                "original_query": user_query
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        await self.state_manager.add_pending_task(clarification_task)
        
        # CLARIFICATIONタスクを実行
        question_message = await self.task_manager.execute_clarification_task(clarification_task)
        await self.state_manager.add_conversation_entry("assistant", question_message)
        return question_message
    
    async def process_clarification_response(self, user_query: str) -> str:
        """
        CLARIFICATIONタスクへの応答処理
        
        Args:
            user_query: ユーザーの応答
            
        Returns:
            処理結果メッセージ
        """
        pending_tasks = self.state_manager.get_pending_tasks()
        
        # CLARIFICATIONタスクを検索
        clarification_task = None
        for task in pending_tasks:
            if task.tool == "CLARIFICATION" and task.status == "pending":
                clarification_task = task
                break
        
        if not clarification_task:
            return "確認が必要なタスクが見つかりません。"
        
        # skipコマンドのチェック
        if user_query.lower() == 'skip':
            return await self._handle_clarification_skip(clarification_task, user_query)
        else:
            return await self._handle_clarification_answer(clarification_task, user_query)
    
    async def _handle_clarification_skip(self, task: TaskState, user_query: str) -> str:
        """
        CLARIFICATIONスキップ処理
        
        Args:
            task: CLARIFICATIONタスク
            user_query: ユーザー入力（'skip'）
            
        Returns:
            スキップ処理結果
        """
        # CLARIFICATIONタスクをスキップ
        await self.state_manager.move_task_to_completed(
            task.task_id, 
            {"user_response": "skipped", "skipped": True}
        )
        
        # 元のクエリに基づいてスマートクエリを生成
        original_query = task.params.get('original_query', '')
        smart_query = self._build_smart_query_for_skip(task, original_query)
        
        self.logger.ulog(f"CLARIFICATION スキップ、スマートクエリで実行: {smart_query}", "info:clarification")
        
        # 新しいタスクリストでの実行は呼び出し元に委譲
        return smart_query
    
    async def _handle_clarification_answer(self, task: TaskState, user_response: str) -> str:
        """
        CLARIFICATION回答処理
        
        Args:
            task: CLARIFICATIONタスク
            user_response: ユーザーの回答
            
        Returns:
            結合されたクエリ
        """
        # CLARIFICATIONタスクを完了としてマーク
        await self.state_manager.move_task_to_completed(
            task.task_id, 
            {"user_response": user_response}
        )
        
        # 元のクエリとユーザー応答を組み合わせて新しいクエリを作成
        original_query = task.params.get('original_query', '')
        question = task.params.get('question', '')
        
        # CLARIFICATIONの質問と回答を含む自然な形式で結合
        if question:
            combined_query = f"{original_query}\n\n[確認回答] {question} → {user_response}"
        else:
            combined_query = f"{original_query}\n\n[追加情報] {user_response}"
        
        self.logger.ulog(f"CLARIFICATION 回答受付、統合クエリで実行", "info:clarification")
        
        return combined_query
    
    def _build_smart_query_for_skip(self, task: TaskState, original_query: str) -> str:
        """
        スキップ時のスマートクエリ構築
        
        Args:
            task: CLARIFICATIONタスク
            original_query: 元のクエリ
            
        Returns:
            スマートクエリ
        """
        question = task.params.get('question', '')
        context = task.params.get('context', '')
        
        # 会話履歴から関連情報を取得
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        
        smart_query = f"""【自動処理モード】
元のリクエスト: {original_query}

確認をスキップされた質問: {question}

会話履歴から推測可能な情報を使用して、
元のリクエストの意図に沿った処理を実行してください。

重要: 追加のCLARIFICATION（確認）は行わず、直接実行してください。

会話履歴:
{recent_context}
"""
        
        return smart_query
    
    def has_pending_clarifications(self) -> bool:
        """
        保留中のCLARIFICATIONタスクがあるかチェック
        
        Returns:
            CLARIFICATIONタスクの有無
        """
        return self.task_manager.has_clarification_tasks()
    
    def get_pending_clarification(self) -> Optional[TaskState]:
        """
        保留中のCLARIFICATIONタスクを取得
        
        Returns:
            CLARIFICATIONタスク（なければNone）
        """
        pending_tasks = self.state_manager.get_pending_tasks()
        
        for task in pending_tasks:
            if task.tool == "CLARIFICATION" and task.status == "pending":
                return task
        
        return None
    
    async def create_clarification_task(self, 
                                      clarification: ClarificationRequest, 
                                      user_query: str,
                                      original_task_spec: Dict[str, Any]) -> TaskState:
        """
        CLARIFICATIONタスクを作成（TaskManagerの機能を移行）
        
        Args:
            clarification: CLARIFICATION要求情報
            user_query: ユーザークエリ
            original_task_spec: 元のタスク仕様
            
        Returns:
            作成されたCLARIFICATIONタスク
        """
        clarification_params = {
            "question": clarification.question,
            "context": clarification.context,
            "user_query": user_query,
            "parameter_name": clarification.parameter_name,
            "suggested_values": clarification.suggested_values or [],
            "original_task": original_task_spec,
            "original_query": user_query
        }
        
        return TaskState(
            task_id=f"clarification_{int(time.time())}_{clarification.parameter_name}",
            tool="CLARIFICATION",
            params=clarification_params,
            description=f"ユーザーに確認: {clarification.question}",
            status="pending",
            created_at=datetime.now().isoformat()
        )
    
    async def execute_clarification_task(self, task: TaskState) -> str:
        """
        CLARIFICATIONタスクを実行（TaskManagerの機能を移行）
        
        Args:
            task: CLARIFICATIONタスク
            
        Returns:
            ユーザーへの確認メッセージ
        """
        question = task.params.get('question', '詳細情報をお教えください')
        context = task.params.get('context', '')
        suggested_values = task.params.get('suggested_values', [])
        
        message_parts = [f"【確認】{question}"]
        
        if context:
            message_parts.append(f"\n背景: {context}")
        
        if suggested_values:
            suggestions = ", ".join(str(v) for v in suggested_values)
            message_parts.append(f"\n候補値: {suggestions}")
        
        message_parts.append("\n\n確認をスキップする場合は 'skip' と入力してください。")
        
        return "".join(message_parts)
    
    def get_clarification_statistics(self) -> Dict[str, Any]:
        """
        CLARIFICATION統計情報を取得
        
        Returns:
            統計情報辞書
        """
        pending = self.state_manager.get_pending_tasks()
        completed = self.state_manager.get_completed_tasks()
        
        return {
            "pending_clarifications": sum(1 for t in pending if t.tool == "CLARIFICATION"),
            "completed_clarifications": sum(1 for t in completed if t.tool == "CLARIFICATION"),
            "skipped_clarifications": sum(1 for t in completed 
                                        if t.tool == "CLARIFICATION" and 
                                        t.result and t.result.get("skipped", False)),
            "answered_clarifications": sum(1 for t in completed 
                                         if t.tool == "CLARIFICATION" and 
                                         t.result and not t.result.get("skipped", False))
        }