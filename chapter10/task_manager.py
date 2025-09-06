#!/usr/bin/env python3
"""
Task Manager for MCP Agent V6
タスク管理システム - CLARIFICATIONタスクと依存関係処理

主要機能:
- タスク作成と実行管理
- CLARIFICATIONタスクの生成
- タスクの依存関係解決
- パラメータ置換とLLMベース解決
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from state_manager import TaskState, StateManager
from utils import safe_str


@dataclass
class ClarificationRequest:
    """ユーザーへの確認要求"""
    question: str
    context: str
    suggested_values: Optional[List[str]] = None
    parameter_name: Optional[str] = None


class TaskManager:
    """
    タスク管理クラス
    
    主要機能:
    - タスクの作成と実行順序管理
    - CLARIFICATIONタスク（確認要求）の生成
    - パラメータの依存関係解決
    - LLMベースのパラメータ推論
    """
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.task_counter = 0
    
    def _generate_task_id(self) -> str:
        """タスクID生成"""
        self.task_counter += 1
        timestamp = datetime.now().strftime("%H%M%S")
        return f"task_{timestamp}_{self.task_counter:03d}"
    
    async def create_tasks_from_list(self, task_list: List[Dict[str, Any]], user_query: str) -> List[TaskState]:
        """
        タスクリストからTaskStateオブジェクトを生成
        
        Args:
            task_list: LLMが生成したタスクリスト
            user_query: 元のユーザー要求
            
        Returns:
            TaskState オブジェクトのリスト
        """
        tasks = []
        
        for i, task_spec in enumerate(task_list):
            task_id = self._generate_task_id()
            
            # paramsから誤って含まれた'description'を除去
            raw_params = task_spec.get('params', {})
            if 'description' in raw_params:
                # LLMが誤ってparamsに含めた場合は削除
                raw_params = {k: v for k, v in raw_params.items() if k != 'description'}
            
            # パラメータの前処理（依存関係やCLARIFICATIONチェック）
            processed_params, clarification_needed = await self._process_task_parameters(
                raw_params, 
                user_query,
                i
            )
            
            # CLARIFICATIONが必要な場合
            if clarification_needed:
                clarification_task = await self._create_clarification_task(
                    clarification_needed, user_query, task_spec
                )
                tasks.append(clarification_task)
                
                # 元のタスクは保留状態で追加
                original_task = TaskState(
                    task_id=self._generate_task_id(),
                    tool=task_spec['tool'],
                    params=processed_params,
                    description=task_spec.get('description', f"{task_spec['tool']}を実行"),
                    status="waiting_for_clarification",
                    created_at=datetime.now().isoformat()
                )
                tasks.append(original_task)
            else:
                # 通常のタスク
                task = TaskState(
                    task_id=task_id,
                    tool=task_spec['tool'],
                    params=processed_params,
                    description=task_spec.get('description', f"{task_spec['tool']}を実行"),
                    status="pending",
                    created_at=datetime.now().isoformat()
                )
                tasks.append(task)
        
        return tasks
    
    async def _process_task_parameters(
        self, 
        params: Dict[str, Any], 
        user_query: str, 
        task_index: int
    ) -> Tuple[Dict[str, Any], Optional[ClarificationRequest]]:
        """
        タスクパラメータを処理し、CLARIFICATIONが必要かチェック
        
        Args:
            params: タスクのパラメータ
            user_query: ユーザーの元の要求
            task_index: タスクのインデックス
            
        Returns:
            (処理済みパラメータ, CLARIFICATION要求)
        """
        processed_params = params.copy()
        
        # 各パラメータをチェック
        for param_name, param_value in params.items():
            if isinstance(param_value, str):
                # LLMが直接解決するため、そのまま保持
                processed_params[param_name] = param_value
        
        return processed_params, None
    
    
    
    async def _create_clarification_task(
        self, 
        clarification: ClarificationRequest, 
        user_query: str,
        original_task_spec: Dict[str, Any]
    ) -> TaskState:
        """CLARIFICATION タスクを作成"""
        
        clarification_params = {
            "question": clarification.question,
            "context": clarification.context,
            "user_query": user_query,
            "parameter_name": clarification.parameter_name,
            "suggested_values": clarification.suggested_values or [],
            "original_task": original_task_spec
        }
        
        return TaskState(
            task_id=self._generate_task_id(),
            tool="CLARIFICATION",
            params=clarification_params,
            description=f"ユーザーに確認: {clarification.question}",
            status="pending",
            created_at=datetime.now().isoformat()
        )
    
    async def execute_clarification_task(self, task: TaskState) -> str:
        """
        CLARIFICATIONタスクを実行
        
        Args:
            task: CLARIFICATIONタスク
            
        Returns:
            ユーザーへの質問メッセージ
        """
        params = task.params
        question = params['question']
        context = params.get('context', '')
        suggested_values = params.get('suggested_values', [])
        
        # ユーザーフレンドリーな質問形式を生成
        message_parts = [f"### 確認が必要です\n\n{question}"]
        
        if context:
            message_parts.append(f"\n**背景情報:**\n{context}")
        
        if suggested_values:
            suggestions = "\n".join([f"- {value}" for value in suggested_values])
            message_parts.append(f"\n**例:**\n{suggestions}")
        
        message_parts.append(f"\n> 回答をお待ちしています。（空行または'skip'と入力でスキップできます）")
        
        return "\n".join(message_parts)
    
    
    
    
    
    def get_next_executable_task(self) -> Optional[TaskState]:
        """実行可能な次のタスクを取得"""
        pending_tasks = self.state_manager.get_pending_tasks()
        
        for task in pending_tasks:
            if task.status == "pending":
                return task
        
        return None
    
    def has_clarification_tasks(self) -> bool:
        """CLARIFICATIONタスクがあるかチェック"""
        pending_tasks = self.state_manager.get_pending_tasks()
        
        for task in pending_tasks:
            if task.tool == "CLARIFICATION" and task.status == "pending":
                return True
        
        return False
    
    
    async def handle_clarification(self, task: TaskState, user_input: str, conversation_manager, state_manager) -> str:
        """
        CLARIFICATION処理の統合関数
        
        Args:
            task: CLARIFICATIONタスク
            user_input: ユーザー入力（'skip'またはクエリ）
            conversation_manager: 会話管理
            state_manager: 状態管理
            
        Returns:
            次に実行するクエリ
        """
        if user_input.lower().strip() == 'skip' or user_input.strip() == '':
            # スキップ処理
            await state_manager.move_task_to_completed(
                task.task_id, 
                {"user_response": "skipped", "skipped": True}
            )
            
            smart_query = self._build_smart_query_for_skip(task, conversation_manager)
            await state_manager.set_user_query(smart_query, "TOOL")
            return smart_query
        else:
            # 通常応答処理
            await state_manager.move_task_to_completed(
                task.task_id, 
                {"user_response": user_input}
            )
            
            combined_query = self._combine_queries(task, user_input)
            await state_manager.set_user_query(combined_query, "TOOL")
            return combined_query
    
    # 互換性維持のための旧関数（将来削除予定）
    async def handle_clarification_skip(self, task: TaskState, conversation_manager, state_manager) -> str:
        """互換性維持のための旧関数"""
        return await self.handle_clarification(task, 'skip', conversation_manager, state_manager)
    
    async def handle_clarification_response(self, task: TaskState, user_response: str, state_manager) -> str:
        """互換性維持のための旧関数"""
        return await self.handle_clarification(task, user_response, None, state_manager)
    
    def _build_smart_query_for_skip(self, task: TaskState, conversation_manager) -> str:
        """スキップ時のスマートクエリ生成"""
        original_query = task.params.get("user_query", "")
        question = task.params.get("question", "")
        context = conversation_manager.get_recent_context(max_items=5, include_results=True)
        
        return f"""以下の状況で処理を実行してください：

元のリクエスト: {original_query}
確認したかった情報: {question}

ユーザーが質問をスキップしました。
会話履歴から推測できる値があればそれを使い、
推測できない場合は適切なデフォルト値や一般的な例を使って、
元のリクエストの意図に沿った処理を実行してください。

重要: 追加のCLARIFICATION（確認）は行わず、直接実行してください。

会話履歴:
{context}"""
    
    def _combine_queries(self, task: TaskState, user_response: str) -> str:
        """クエリの組み合わせ"""
        original_query = task.params.get("user_query", "")
        return f"{original_query}。{user_response}。"
    
    def get_task_summary(self) -> Dict[str, Any]:
        """タスクの概要を取得"""
        pending = self.state_manager.get_pending_tasks()
        completed = self.state_manager.get_completed_tasks()
        
        return {
            "total_tasks": len(pending) + len(completed),
            "pending_tasks": len(pending),
            "completed_tasks": len(completed),
            "clarification_tasks": sum(1 for t in pending if t.tool == "CLARIFICATION"),
            "waiting_tasks": sum(1 for t in pending if t.status == "waiting_for_clarification"),
            "executable_tasks": sum(1 for t in pending if t.status == "pending"),
            "has_work": len(pending) > 0
        }