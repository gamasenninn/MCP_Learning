#!/usr/bin/env python3
"""
Display Manager for MCP Agent
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


from utils import safe_str


class DisplayManager:
    """視覚的フィードバックを管理するクラス"""
    
    def __init__(self, show_timing: bool = True, show_thinking: bool = False, logger=None):
        """
        Args:
            show_timing: 実行時間を表示するかどうか
            show_thinking: 思考過程を表示するかどうか（show_tool_call内で使用）
            logger: ログ出力用のLoggerインスタンス（Noneの場合は直接print）
        """
        self.show_timing = show_timing
        self.show_thinking = show_thinking
        self.logger = logger
        self.start_time = time.monotonic()
    
    def show_banner(self):
        """バナーを表示"""
        print("=" * 60)
        print(" MCP Agent - Interactive Dialogue Engine")
        print(" Claude Code風の対話型エージェント")
        print("=" * 60)
    
    
    def show_analysis(self, message: str):
        """分析中のメッセージを表示"""
        if self.logger:
            self.logger.ulog(f"{message}", "info:analysis", show_level=True)
        else:
            print(f"[分析] {message}")
    
    def show_task_list(self, tasks: List[Dict], current_index: int = -1, 
                       completed: List[int] = None, failed: List[int] = None,
                       header: str = "[タスク一覧]"):
        """
        統一されたタスクリスト表示
        
        Args:
            tasks: タスクのリスト
            current_index: 現在実行中のタスクインデックス
            completed: 完了タスクのインデックスリスト
            failed: 失敗タスクのインデックスリスト
            header: 表示するヘッダー
        """
        if not tasks:
            return
        
        print(f"\n{header}")
        for i, task in enumerate(tasks):
            # ステータス判定を統一
            status = self._get_task_status(i, current_index, completed, failed, 
                                           task.get('status', 'pending'))
            icon = self._get_status_icon(status)
            description = task.get('description', task.get('tool', 'Unknown'))
            
            line = f"  {icon} {description}"
            
            # タイミング表示
            if self.show_timing and task.get('duration'):
                line += f" ({task['duration']:.1f}秒)"
            elif status == 'running':
                line += " [実行中...]"
            
            print(line)
    
    def _get_task_status(self, index: int, current_index: int, completed: List[int] = None, 
                        failed: List[int] = None, default_status: str = 'pending') -> str:
        """タスクステータスを統一的に判定"""
        if failed and index in failed:
            return 'failed'
        if completed and index in completed:
            return 'completed'
        if index == current_index:
            return 'running'
        return default_status
    
    def _get_status_icon(self, status: str) -> str:
        """ステータスアイコンのマッピング"""
        icons = {
            'completed': '[x]',
            'failed': '[!]',
            'running': '[>]',
            'pending': '[ ]'
        }
        return icons.get(status, '[ ]')
    
    def show_checklist(self, tasks: List[Dict], current: int = -1):
        """チェックリスト形式でタスク一覧を表示（統一版）"""
        self.show_task_list(tasks, current)
    
    def update_checklist(self, tasks: List[Dict], current: int, completed: List[int] = None, failed: List[int] = None):
        """チェックリストの状態を更新して表示"""
        if not tasks:
            return
        
        # 前の表示をクリア（簡易版）
        print("\n" + "=" * 40)
        
        # 統一されたタスクリスト表示を使用
        self.show_task_list(tasks, current, completed, failed, "[進行状況]")
    
    
    def show_step_start(self, step_num: int, total: int, description: str):
        """ステップ開始を表示"""
        print(f"\n[ステップ {step_num}/{total}] {description}")
        if self.show_timing:
            print(f"  開始時刻: {datetime.now().strftime('%H:%M:%S')}")
    
    def show_step_complete(self, description: str, duration: float, success: bool = True):
        """ステップ完了を表示"""
        status = "[完了]" if success else "[失敗]"
        line = f"{status} {description}"
        
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
    
    
    def show_error(self, message: str, suggestion: str = None):
        """エラーメッセージと対処法を表示"""
        print(f"[エラー] {message}")
        if suggestion:
            print(f"  -> 対処: {suggestion}")
    
    def show_retry(self, attempt: int, max_attempts: int, tool: str):
        """リトライ情報を表示"""
        print(f"[リトライ {attempt}/{max_attempts}] {tool} を再実行中...")
    
    def show_context_info(self, context_items: int):
        """会話文脈情報を表示"""
        if context_items > 0:
            print(f"[文脈] 過去{context_items}件の会話を参考にします")
    
    def show_tool_call(self, tool: str, params: Dict[str, Any]):
        """ツール呼び出し情報を表示"""
        print(f"  -> {tool} を実行中...")
        if self.show_thinking and params:
            # パラメータを簡潔に表示（サロゲート文字を安全に処理）
            param_items = []
            for k, v in params.items():
                safe_key = safe_str(k)
                safe_value = safe_str(v)
                param_items.append(f"{safe_key}={safe_value}")
            
            param_str = ", ".join(param_items)
            if len(param_str) > 60:
                param_str = param_str[:57] + "..."
            print(f"     パラメータ: {param_str}")
    
    
    def get_elapsed_time(self) -> float:
        """開始からの経過時間を取得"""
        return time.monotonic() - self.start_time
    
    
    def show_welcome(self, servers: int, tools: int, ui_mode: str):
        """初期化完了後のウェルカムメッセージ"""
        print("=" * 50)
        print("         MCP Agent - 準備完了")
        print("=" * 50)
        print(f"  接続サーバー: {servers}個")
        print(f"  利用可能ツール: {tools}個")
        print(f"  UIモード: {ui_mode}")
        print("=" * 50)