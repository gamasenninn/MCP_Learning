#!/usr/bin/env python3
"""
Display Manager for MCP Agent V4
Claude Code風の視覚的フィードバックを提供

V4での特徴：
- チェックボックス付きタスクリスト
- プログレス表示
- 実行時間表示
- Windows環境対応（絵文字なし）
"""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime


class DisplayManager:
    """視覚的フィードバックを管理するクラス"""
    
    def __init__(self, show_timing: bool = True, show_thinking: bool = False):
        """
        Args:
            show_timing: 実行時間を表示するかどうか
            show_thinking: 思考過程を表示するかどうか
        """
        self.show_timing = show_timing
        self.show_thinking = show_thinking
        self.start_time = time.time()
    
    def show_banner(self):
        """V4のバナーを表示"""
        print("=" * 60)
        print(" MCP Agent V4 - Interactive Dialogue Engine")
        print(" Claude Code風の対話型エージェント")
        print("=" * 60)
    
    def show_thinking(self, message: str):
        """思考中のメッセージを表示"""
        if self.show_thinking:
            print(f"[思考] {message}")
    
    def show_analysis(self, message: str):
        """分析中のメッセージを表示"""
        print(f"[分析] {message}")
    
    def show_task_list(self, tasks: List[Dict], current_index: int = -1):
        """
        チェックボックス付きタスクリストを表示
        
        Args:
            tasks: タスクのリスト
            current_index: 現在実行中のタスクインデックス
        """
        if not tasks:
            return
        
        print("\n[タスク一覧]")
        for i, task in enumerate(tasks):
            status_icon = self._get_status_icon(i, current_index, task.get('status', 'pending'))
            description = task.get('description', task.get('tool', 'Unknown'))
            
            line = f"  {status_icon} {description}"
            
            # 実行時間を表示
            if self.show_timing and task.get('duration'):
                line += f" ({task['duration']:.1f}秒)"
            
            print(line)
    
    def _get_status_icon(self, index: int, current_index: int, status: str) -> str:
        """タスクの状態に応じたアイコンを返す"""
        if status == 'completed':
            return "[x]"  # 完了
        elif status == 'failed':
            return "[!]"  # 失敗
        elif index == current_index:
            return "[>]"  # 実行中
        else:
            return "[ ]"  # 未実行
    
    def show_checklist(self, tasks: List[Dict], current: int = -1):
        """チェックリスト形式でタスク一覧を表示"""
        if not tasks:
            return
        
        print("\n[タスクリスト]")
        for i, task in enumerate(tasks):
            icon = self._get_checklist_icon(i, current, task.get('status', 'pending'))
            description = task.get('description', task.get('tool', 'Unknown'))
            print(f"  {icon} {description}")
    
    def update_checklist(self, tasks: List[Dict], current: int, completed: List[int] = None, failed: List[int] = None):
        """チェックリストの状態を更新して表示"""
        if not tasks:
            return
        
        # 前の表示をクリア（簡易版）
        print("\n" + "=" * 40)
        print("[進行状況]")
        
        for i, task in enumerate(tasks):
            # ステータスを判定
            if failed and i in failed:
                status = 'failed'
            elif completed and i in completed:
                status = 'completed'
            elif i == current:
                status = 'running'
            else:
                status = 'pending'
            
            icon = self._get_checklist_icon(i, current, status)
            description = task.get('description', task.get('tool', 'Unknown'))
            
            line = f"  {icon} {description}"
            
            # 実行時間を表示（完了した場合）
            if self.show_timing and status == 'completed' and task.get('duration'):
                line += f" ({task['duration']:.1f}秒)"
            elif status == 'running':
                line += " [実行中...]"
            
            print(line)
    
    def _get_checklist_icon(self, index: int, current_index: int, status: str) -> str:
        """チェックリストのアイコンを取得"""
        if status == 'completed':
            return "[x]"  # 完了
        elif status == 'failed':
            return "[!]"  # 失敗
        elif status == 'running' or index == current_index:
            return "[>]"  # 実行中
        else:
            return "[ ]"  # 未実行
    
    def show_step_start(self, step_num: int, total: int, description: str):
        """ステップ開始を表示"""
        print(f"\n[ステップ {step_num}/{total}] {description}")
        if self.show_timing:
            print(f"  開始時刻: {datetime.now().strftime('%H:%M:%S')}")
    
    def show_step_complete(self, description: str, duration: float, success: bool = True):
        """ステップ完了を表示"""
        status = "[完了]" if success else "[失敗]"
        line = f"  {status} {description}"
        
        if self.show_timing:
            line += f" ({duration:.1f}秒)"
        
        print(line)
    
    def show_progress(self, current: int, total: int):
        """プログレス表示"""
        if total <= 1:
            return
        
        percentage = int((current / total) * 100)
        filled = int((current / total) * 20)
        bar = "=" * filled + "-" * (20 - filled)
        
        print(f"[{bar}] {percentage}% ({current}/{total})")
    
    def show_result_summary(self, total_tasks: int, successful: int, failed: int, 
                          total_duration: float):
        """実行結果サマリーを表示"""
        print("\n" + "=" * 50)
        print("実行結果サマリー")
        print("=" * 50)
        print(f"実行タスク: {total_tasks}個")
        print(f"成功: {successful}個 | 失敗: {failed}個")
        
        if self.show_timing:
            print(f"総実行時間: {total_duration:.1f}秒")
        
        success_rate = (successful / total_tasks * 100) if total_tasks > 0 else 0
        print(f"成功率: {success_rate:.0f}%")
    
    def show_error(self, message: str, suggestion: str = None):
        """エラーメッセージと対処法を表示"""
        print(f"[エラー] {message}")
        if suggestion:
            print(f"  -> 対処: {suggestion}")
    
    def show_retry(self, attempt: int, max_attempts: int, tool: str):
        """リトライ情報を表示"""
        print(f"  [リトライ {attempt}/{max_attempts}] {tool} を再実行中...")
    
    def show_context_info(self, context_items: int):
        """会話文脈情報を表示"""
        if context_items > 0:
            print(f"[文脈] 過去{context_items}件の会話を参考にします")
    
    def show_tool_call(self, tool: str, params: Dict[str, Any]):
        """ツール呼び出し情報を表示"""
        print(f"  -> {tool} を実行中...")
        if self.show_thinking and params:
            # パラメータを簡潔に表示
            param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
            if len(param_str) > 60:
                param_str = param_str[:57] + "..."
            print(f"     パラメータ: {param_str}")
    
    def show_waiting(self, message: str = "処理中"):
        """待機中のメッセージ"""
        print(f"  {message}...")
    
    def get_elapsed_time(self) -> float:
        """開始からの経過時間を取得"""
        return time.time() - self.start_time
    
    def clear_line(self):
        """現在行をクリア（プログレス更新用）"""
        print("\r" + " " * 80 + "\r", end="", flush=True)