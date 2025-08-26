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

import re
import json
import asyncio
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
    
    def __init__(self, state_manager: StateManager, llm_client=None):
        self.state_manager = state_manager
        self.llm_client = llm_client
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
            
            # パラメータの前処理（依存関係やCLARIFICATIONチェック）
            processed_params, clarification_needed = await self._process_task_parameters(
                task_spec.get('params', {}), 
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
                # 不明な参照のチェック
                clarification = await self._check_for_unknown_references(
                    param_name, param_value, user_query
                )
                
                if clarification:
                    return processed_params, clarification
                
                # 依存関係の解決
                resolved_value = await self._resolve_parameter_dependencies(
                    param_value, task_index
                )
                processed_params[param_name] = resolved_value
        
        return processed_params, None
    
    async def _check_for_unknown_references(
        self, 
        param_name: str, 
        param_value: str, 
        user_query: str
    ) -> Optional[ClarificationRequest]:
        """
        不明な参照（「私の年齢」等）をチェックしてCLARIFICATION要求を生成
        
        Args:
            param_name: パラメータ名
            param_value: パラメータ値
            user_query: ユーザーの要求
            
        Returns:
            CLARIFICATION要求（必要な場合）
        """
        # 不明な参照パターンを検出
        unknown_patterns = [
            r'私の.*',
            r'自分の.*',
            r'僕の.*', 
            r'俺の.*',
            r'当社の.*',
            r'うちの.*',
            r'この.*',
            r'その.*'
        ]
        
        for pattern in unknown_patterns:
            if re.search(pattern, param_value):
                # ユーザーに確認が必要
                return ClarificationRequest(
                    question=f"「{param_value}」について教えてください。",
                    context=f"要求: {user_query}\nパラメータ「{param_name}」で「{param_value}」が指定されていますが、具体的な値がわかりません。",
                    parameter_name=param_name
                )
        
        # 計算に関する不明な値をチェック
        if self._requires_calculation_clarification(param_value, user_query):
            return await self._create_calculation_clarification(param_name, param_value, user_query)
        
        return None
    
    def _requires_calculation_clarification(self, param_value: str, user_query: str) -> bool:
        """計算で値の確認が必要かチェック"""
        # 具体的な数値が含まれていない計算要求
        calculation_keywords = ['計算', '足し算', '引き算', '掛け算', '割り算', '合計', '平均']
        has_calculation = any(keyword in user_query for keyword in calculation_keywords)
        
        if has_calculation:
            # 具体的な数値が含まれているかチェック
            import re
            numbers = re.findall(r'\d+', user_query)
            return len(numbers) < 2  # 2つ未満の数値しかない場合は確認が必要
        
        return False
    
    async def _create_calculation_clarification(
        self, 
        param_name: str, 
        param_value: str, 
        user_query: str
    ) -> ClarificationRequest:
        """計算に関するCLARIFICATION要求を生成"""
        return ClarificationRequest(
            question="計算に必要な数値を教えてください。",
            context=f"要求: {user_query}\n具体的な数値や値が必要です。どのような値を使って計算しますか？",
            suggested_values=["例: 数値を入力してください"],
            parameter_name=param_name
        )
    
    async def _resolve_parameter_dependencies(self, param_value: str, task_index: int) -> str:
        """
        パラメータの依存関係を解決
        
        Args:
            param_value: パラメータ値
            task_index: 現在のタスクインデックス
            
        Returns:
            解決済みパラメータ値
        """
        # 前のタスクの結果参照パターン
        dependency_patterns = [
            r'\{\{previous_result\}\}',
            r'\{\{task_(\d+)\.(\w+)\}\}',
            r'取得した(\w+)',
            r'前回の結果'
        ]
        
        resolved_value = param_value
        
        for pattern in dependency_patterns:
            if re.search(pattern, param_value):
                # 依存関係マーカーとして保持（実行時に解決）
                resolved_value = f"DEPENDENCY:{param_value}"
                break
        
        return resolved_value
    
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
        
        message_parts.append(f"\n> 回答をお待ちしています。ESCキーで作業を中断することもできます。")
        
        return "\n".join(message_parts)
    
    async def resolve_clarification(self, task_id: str, user_response: str) -> bool:
        """
        CLARIFICATION の回答を処理し、保留中のタスクを更新
        
        Args:
            task_id: CLARIFICATIONタスクのID
            user_response: ユーザーの回答
            
        Returns:
            成功フラグ
        """
        # 完了したCLARIFICATIONタスクを取得
        completed_tasks = self.state_manager.get_completed_tasks()
        clarification_task = None
        
        for task in completed_tasks:
            if task.task_id == task_id and task.tool == "CLARIFICATION":
                clarification_task = task
                break
        
        if not clarification_task:
            return False
        
        # 保留中のタスクを更新
        pending_tasks = self.state_manager.get_pending_tasks()
        updated = False
        
        for task in pending_tasks:
            if task.status == "waiting_for_clarification":
                # パラメータを更新
                param_name = clarification_task.params.get('parameter_name')
                if param_name and param_name in task.params:
                    task.params[param_name] = user_response
                    task.status = "pending"
                    task.updated_at = datetime.now().isoformat()
                    updated = True
        
        return updated
    
    async def resolve_task_dependencies(self, task: TaskState, completed_tasks: List[TaskState]) -> TaskState:
        """
        タスクの依存関係を実行時に解決
        
        Args:
            task: 実行するタスク
            completed_tasks: 完了済みタスクのリスト
            
        Returns:
            依存関係が解決されたタスク
        """
        resolved_task = TaskState(
            task_id=task.task_id,
            tool=task.tool,
            params=task.params.copy(),
            description=task.description,
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            updated_at=datetime.now().isoformat()
        )
        
        # 各パラメータの依存関係を解決
        for param_name, param_value in task.params.items():
            if isinstance(param_value, str):
                # DEPENDENCY:プレフィックス付き または 直接的な依存関係
                if param_value.startswith("DEPENDENCY:"):
                    original_param = param_value[11:]  # "DEPENDENCY:" を削除
                    resolved_value = await self._resolve_dependency_value(
                        original_param, completed_tasks
                    )
                    resolved_task.params[param_name] = resolved_value
                # 直接的な {previous_result} パターン
                elif "{previous_result}" in param_value or "{{previous_result}}" in param_value:
                    resolved_value = await self._resolve_dependency_value(
                        param_value, completed_tasks
                    )
                    resolved_task.params[param_name] = resolved_value
        
        return resolved_task
    
    async def _resolve_dependency_value(self, dependency_param: str, completed_tasks: List[TaskState]) -> any:
        """依存関係の値を解決"""
        if not completed_tasks:
            return dependency_param
            
        # 最新の結果を取得
        last_result = completed_tasks[-1].result
        
        # {{previous_result}} または {previous_result} パターン
        if "{previous_result}" in dependency_param or "{{previous_result}}" in dependency_param:
            # MCP応答から数値を抽出
            extracted_value = self._extract_numeric_value(last_result)
            if extracted_value is not None:
                return extracted_value
            return str(last_result) if last_result else dependency_param
        
        # {{task_N.field}} パターン
        task_ref_match = re.search(r'\{\{task_(\d+)\.(\w+)\}\}', dependency_param)
        if task_ref_match:
            task_num = int(task_ref_match.group(1)) - 1  # 0-based index
            field_name = task_ref_match.group(2)
            
            if task_num < len(completed_tasks):
                task_result = completed_tasks[task_num].result
                if isinstance(task_result, dict) and field_name in task_result:
                    return task_result[field_name]
        
        # 「取得した○○」パターン
        if "取得した" in dependency_param:
            # まず数値を抽出してみる（計算結果の場合）
            if "取得した結果" in dependency_param:
                extracted_value = self._extract_numeric_value(last_result)
                if extracted_value is not None:
                    return extracted_value
            
            # 辞書形式の結果からフィールドを推測
            if isinstance(last_result, dict):
                # よくあるフィールド名を推測
                common_fields = ['city', 'name', 'location', '都市', '名前', '場所']
                for field in common_fields:
                    if field in last_result:
                        return str(last_result[field])
            
            return str(last_result) if last_result else dependency_param
        
        return dependency_param
    
    def _extract_numeric_value(self, mcp_result) -> any:
        """MCP応答から数値を抽出"""
        if mcp_result is None:
            return None
        
        # CallToolResultオブジェクトを直接処理
        if hasattr(mcp_result, 'data'):
            data = mcp_result.data
            if isinstance(data, (int, float)):
                return data
            elif isinstance(data, str) and data.replace('.', '').replace('-', '').isdigit():
                try:
                    return float(data)
                except ValueError:
                    pass
        
        # structured_contentからの抽出
        if hasattr(mcp_result, 'structured_content') and isinstance(mcp_result.structured_content, dict):
            result_value = mcp_result.structured_content.get('result')
            if isinstance(result_value, (int, float)):
                return result_value
            
        # MCP応答の文字列表現から数値を探す（後方互換性）
        result_str = str(mcp_result)
        
        # structured_content.result を探す
        if 'structured_content' in result_str:
            import re
            struct_match = re.search(r"'result':\s*([0-9.]+)", result_str)
            if struct_match:
                try:
                    return float(struct_match.group(1))
                except ValueError:
                    pass
        
        # data= パターンを探す
        data_match = re.search(r"data=([0-9.]+)", result_str)
        if data_match:
            try:
                return float(data_match.group(1))
            except ValueError:
                pass
        
        # TextContentのtext内の数値を探す
        text_match = re.search(r"text='([^']*)'", result_str)
        if text_match:
            text_content = text_match.group(1)
            number_match = re.search(r'([0-9.]+)', text_content)
            if number_match:
                try:
                    return float(number_match.group(1))
                except ValueError:
                    pass
        
        return None
    
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