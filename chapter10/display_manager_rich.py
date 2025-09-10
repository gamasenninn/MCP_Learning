#!/usr/bin/env python3
"""
Rich-based Display Manager for MCP Agent V4
Claude Code風の美しいUI表示を提供

主な特徴：
- Richライブラリによる美しいUI
- ライブ更新可能なタスクリスト
- 進捗バーとスピナー表示
- 色分けされたステータス表示
- Windows/Mac/Linux対応
"""

import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime


from utils import safe_str, Logger

# Rich imports (optional dependency)
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, MofNCompleteColumn
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.tree import Tree
    from rich.status import Status
    from rich.prompt import Prompt, Confirm
    from rich.layout import Layout
    from rich.text import Text
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class RichDisplayManager:
    """Rich ライブラリを使った美しいUI表示"""
    
    def __init__(self, show_timing: bool = True, show_thinking: bool = False):
        """
        Args:
            show_timing: 実行時間を表示するかどうか
            show_thinking: 思考過程を表示するかどうか
        """
        if not RICH_AVAILABLE:
            raise ImportError("Rich library not available. Please install: pip install rich")
        
        self.show_timing = show_timing
        self.show_thinking = show_thinking
        self.start_time = time.monotonic()
        
        # Rich コンソールを初期化
        self.console = Console()
        
        # 進捗管理
        self.current_progress = None
        self.current_live = None
        
        # 色テーマ
        self.colors = {
            'success': 'green',
            'error': 'red',
            'warning': 'yellow',
            'info': 'cyan',
            'accent': 'bright_blue',
            'muted': 'bright_black'
        }
    
    def show_banner(self):
        """美しいバナーを表示"""
        banner = Panel.fit(
            "[bold bright_blue]MCP Agent[/bold bright_blue]\n"
            "[italic]Interactive Dialogue Engine with Rich UI[/italic]\n"
            "[dim]Claude Code風の対話型エージェント[/dim]",
            style="bright_blue",
            padding=(1, 2)
        )
        self.console.print(banner)
    
    def show_thinking(self, message: str):
        """思考中のメッセージを表示（スピナー付き）"""
        if self.show_thinking:
            with Status(f"[dim]{message}[/dim]", spinner="dots"):
                time.sleep(0.1)  # 短時間表示
    
    def show_analysis(self, message: str):
        """分析中のメッセージを表示"""
        self.console.print(f"[{self.colors['info']}][分析][/] {message}")
    def show_task_list(self, tasks: List[Dict], current_index: int = -1):
        """タスク一覧を表示（BasicDisplayManagerとの互換性のため）"""
        self.show_checklist(tasks, current_index)
    
    def show_checklist(self, tasks: List[Dict], current: int = -1):
        """美しいチェックリスト表示"""
        if not tasks:
            return
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Status", width=4)
        table.add_column("Task", min_width=30)
        table.add_column("Duration", justify="right", width=8)
        
        self.console.print("\n[bold]タスクリスト[/bold]")
        
        for i, task in enumerate(tasks):
            status_text, status_color = self._get_status_display(i, current, task.get('status', 'pending'))
            description = task.get('description', task.get('tool', 'Unknown'))
            
            # 実行時間の表示
            duration_text = ""
            if self.show_timing and task.get('duration'):
                duration_text = f"{task['duration']:.1f}s"
            
            table.add_row(
                f"[{status_color}]{status_text}[/]",
                description,
                f"[{self.colors['muted']}]{duration_text}[/]"
            )
        
        self.console.print(table)
    
    def update_checklist_live(self, tasks: List[Dict], current: int, completed: List[int] = None, failed: List[int] = None):
        """ライブ更新可能なチェックリスト"""
        if not tasks:
            return
        
        def make_table():
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Status", width=4)
            table.add_column("Task", min_width=30)
            table.add_column("Duration", justify="right", width=8)
            
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
                
                status_text, status_color = self._get_status_display(i, current, status)
                description = task.get('description', task.get('tool', 'Unknown'))
                
                # 実行時間の表示
                duration_text = ""
                if self.show_timing and status == 'completed' and task.get('duration'):
                    duration_text = f"{task['duration']:.1f}s"
                elif status == 'running':
                    duration_text = "[実行中]"
                
                table.add_row(
                    f"[{status_color}]{status_text}[/]",
                    description,
                    f"[{self.colors['muted']}]{duration_text}[/]"
                )
            
            return Panel(table, title="[bold]進行状況[/bold]", border_style="bright_blue")
        
        # ライブ更新
        if self.current_live:
            self.current_live.update(make_table())
        else:
            self.console.print(make_table())
    
    def update_checklist(self, tasks: List[Dict], current: int, completed: List[int] = None, failed: List[int] = None):
        """チェックリストの状態を更新して表示（非ライブ版）"""
        self.console.clear()
        self.update_checklist_live(tasks, current, completed, failed)
    
    def _get_status_display(self, index: int, current_index: int, status: str) -> tuple[str, str]:
        """ステータスアイコンと色を取得"""
        if status == 'completed':
            return "✓", self.colors['success']
        elif status == 'failed':
            return "✗", self.colors['error']
        elif status == 'running' or index == current_index:
            return "▶", self.colors['warning']
        else:
            return "○", self.colors['muted']
    
    def show_step_start(self, step_num: int, total: int, description: str):
        """ステップ開始を美しく表示"""
        step_text = Text()
        step_text.append(f"[ステップ {step_num}", style=self.colors['info'])
        if total != "?":
            step_text.append(f"/{total}", style=self.colors['muted'])
        step_text.append(f"] {description}", style="bold")
        
        panel = Panel(step_text, border_style=self.colors['info'])
        self.console.print(panel)
        
        if self.show_timing:
            self.console.print(f"  [dim]開始時刻: {datetime.now().strftime('%H:%M:%S')}[/dim]")
    
    def show_step_complete(self, description: str, duration: float, success: bool = True):
        """ステップ完了を美しく表示"""
        status_icon = "✓" if success else "✗"
        status_color = self.colors['success'] if success else self.colors['error']
        
        text = f"[{status_color}]{status_icon}[/] {description}"
        
        if self.show_timing:
            text += f" [dim]({duration:.1f}s)[/dim]"
        
        self.console.print(f"  {text}")
    
    def show_progress_bar(self, current: int, total: int, description: str = "Processing"):
        """美しい進捗バー表示"""
        if total <= 1:
            return
        
        if not self.current_progress:
            self.current_progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=self.console
            )
            self.current_progress.start()
        
        # タスクを更新
        task_id = self.current_progress.add_task(description, total=total)
        self.current_progress.update(task_id, completed=current)
    
    def show_result_panel(self, title: str, content: str, success: bool = True):
        """結果をパネルで美しく表示"""
        border_style = self.colors['success'] if success else self.colors['error']
        
        # 内容がJSONの場合は構文ハイライト
        try:
            # サロゲート文字を除去してからJSON処理
            clean_content = safe_str(content)
            json.loads(clean_content)
            formatted_content = Syntax(clean_content, "json", theme="monokai", line_numbers=False)
        except (json.JSONDecodeError, ValueError):
            # JSONでない場合は普通のテキスト（サロゲート文字も除去）
            formatted_content = safe_str(content)
        
        panel = Panel(
            formatted_content,
            title=f"[bold]{title}[/bold]",
            border_style=border_style,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def show_result_summary(self, total_tasks: int, successful: int, failed: int, 
                          total_duration: float):
        """美しい結果サマリー"""
        
        # 成功率の計算
        success_rate = (successful / total_tasks * 100) if total_tasks > 0 else 0
        
        # サマリーテーブル
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        
        table.add_row("実行タスク", f"{total_tasks}個")
        table.add_row("成功", f"[{self.colors['success']}]{successful}個[/]")
        table.add_row("失敗", f"[{self.colors['error']}]{failed}個[/]")
        
        if self.show_timing:
            table.add_row("総実行時間", f"{total_duration:.1f}秒")
        
        # 成功率の色分け
        rate_color = self.colors['success'] if success_rate >= 80 else self.colors['warning'] if success_rate >= 60 else self.colors['error']
        table.add_row("成功率", f"[{rate_color}]{success_rate:.0f}%[/]")
        
        panel = Panel(
            table,
            title="[bold]実行結果サマリー[/bold]",
            border_style=self.colors['accent']
        )
        
        self.console.print(panel)
    
    def show_error(self, message: str, suggestion: str = None):
        """美しいエラー表示"""
        error_text = f"[{self.colors['error']}]✗ {message}[/]"
        
        if suggestion:
            error_text += f"\n[{self.colors['info']}]💡 対処: {suggestion}[/]"
        
        panel = Panel(
            error_text,
            title="[bold red]エラー[/bold red]",
            border_style=self.colors['error']
        )
        
        self.console.print(panel)
    
    def show_retry(self, attempt: int, max_attempts: int, tool: str):
        """リトライ情報を美しく表示"""
        with Status(f"[{self.colors['warning']}]リトライ {attempt}/{max_attempts}: {tool}[/]", spinner="dots2"):
            time.sleep(1)
    
    def show_context_info(self, context_items: int):
        """会話文脈情報を美しく表示"""
        if context_items > 0:
            self.console.print(f"[{self.colors['info']}]📝 過去{context_items}件の会話を参考にします[/]")
    
    def show_tool_call(self, tool: str, params: Dict[str, Any]):
        """ツール呼び出し情報を美しく表示"""
        self.console.print(f"  [dim]→ {tool} を実行中...[/dim]")
        
        if self.show_thinking and params:
            # Pythonコード実行と思われるパラメータを探す
            code_param = None
            code_key = None
            for key in ['code', 'python_code', 'script', 'command']:
                if key in params and isinstance(params[key], str):
                    code_param = params[key]
                    code_key = key
                    break
            
            if code_param:
                self.console.print(f"    [dim]実行するコード:[/dim]")
                from rich.syntax import Syntax
                # サロゲート文字を除去してからSyntax処理
                clean_code = safe_str(code_param)
                code_display = Syntax(clean_code, "python", theme="monokai", line_numbers=True)
                self.console.print(code_display)
                
                # その他のパラメータがあれば表示
                other_params = {k: v for k, v in params.items() if k != code_key}
                if other_params:
                    param_str = safe_str(str(other_params))
                    if len(param_str) < 100:
                        param_text = param_str
                    else:
                        param_text = param_str[:97] + "..."
                    self.console.print(f"    [dim]その他のパラメータ: {param_text}[/dim]")
            else:
                # 通常のパラメータ表示
                param_str = safe_str(str(params))
                if len(param_str) < 200:
                    param_text = param_str
                else:
                    param_text = param_str[:197] + "..."
                self.console.print(f"    [dim]パラメータ: {param_text}[/dim]")
    
    def show_waiting(self, message: str = "処理中"):
        """待機中の美しいスピナー表示"""
        with Status(f"[dim]{message}...[/dim]", spinner="dots"):
            time.sleep(0.5)
    
    def show_markdown_result(self, content: str):
        """Markdownコンテンツを美しく表示"""
        md = Markdown(content)
        panel = Panel(md, border_style=self.colors['accent'])
        self.console.print(panel)
    
    def show_task_tree(self, tasks: List[Dict], current: int = -1):
        """タスクをツリー形式で表示"""
        tree = Tree("[bold]タスク実行計画[/bold]")
        
        for i, task in enumerate(tasks):
            status_text, status_color = self._get_status_display(i, current, task.get('status', 'pending'))
            description = task.get('description', task.get('tool', 'Unknown'))
            
            branch_text = f"[{status_color}]{status_text}[/] {description}"
            
            if task.get('duration') and self.show_timing:
                branch_text += f" [dim]({task['duration']:.1f}s)[/dim]"
            
            tree.add(branch_text)
        
        self.console.print(tree)
    
    def input_prompt(self, message: str = "Agent") -> str:
        """美しい入力プロンプト"""
        return Prompt.ask(f"[bold {self.colors['accent']}]{message}>[/]")
    
    def confirm_prompt(self, message: str) -> bool:
        """確認プロンプト"""
        return Confirm.ask(message)
    
    def get_elapsed_time(self) -> float:
        """開始からの経過時間を取得"""
        return time.monotonic() - self.start_time
    
    def clear_screen(self):
        """画面クリア"""
        self.console.clear()
    
    def show_welcome(self, servers: int, tools: int, ui_mode: str):
        """初期化完了後のウェルカムメッセージ（Rich版）"""
        from rich.panel import Panel
        from rich.align import Align
        
        content = f"""[bold cyan]MCP Agent[/bold cyan] - [green]準備完了[/green]
        
[dim]接続サーバー:[/dim] [yellow]{servers}個[/yellow]
[dim]利用可能ツール:[/dim] [yellow]{tools}個[/yellow]
[dim]UIモード:[/dim] [magenta]{ui_mode}[/magenta]"""
        
        panel = Panel(
            Align.center(content),
            title="[bold blue]Model Context Protocol Agent[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
    


# Rich が利用できない場合のフォールバック
if not RICH_AVAILABLE:
    from display_manager import DisplayManager
    
    class RichDisplayManager(DisplayManager):
        """Rich未インストール時のフォールバック"""
        def __init__(self, *args, **kwargs):
            # loggerが渡されていればwarning使用、なければLoggerを直接使用
            logger = kwargs.get('logger')
            if logger:
                logger.ulog("Rich library not available. Using basic display.", "warning", show_level=True)
            else:
                Logger().ulog("Rich library not available. Using basic display.", "warning:display", show_level=True)
            super().__init__(*args, **kwargs)