#!/usr/bin/env python3
"""
MCP Agent REPL Interface
対話的なコマンドラインインターフェース

主な機能:
- コマンドライン対話型インターフェース
- 空行によるCLARIFICATIONスキップ機能
- Rich/Simple UI対応
- Ctrl+C割り込み処理
"""

import asyncio
from mcp_agent import MCPAgent
from repl_commands import CommandManager
from interrupt_manager import get_interrupt_manager
from task_executor import EscInterrupt
from utils import Logger

# prompt_toolkit support
try:
    from prompt_toolkit import PromptSession
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


def create_prompt_session(agent):
    """シンプルなプロンプトセッション作成（補完・履歴機能付き、ESCバインドなし）"""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    
    try:
        # ESCキーバインドは設定せず、デフォルトの入力機能のみ使用
        return PromptSession()
    
    except Exception:
        # Windows環境やCI環境でのコンソールエラーを無視
        return None


async def main():
    """メイン実行関数"""
    Logger().ulog("MCP Agent を起動しています...", "info:startup", always_print=True)
    agent = MCPAgent()
    await agent.initialize()
    
    # コマンドマネージャーを初期化
    command_manager = CommandManager(agent)
    # agentからも参照できるように設定
    agent.command_manager = command_manager
    
    try:
        # 初期化完了後のウェルカムメッセージ
        agent.display.show_welcome(
            servers=len(agent.connection_manager.clients),
            tools=len(agent.connection_manager.tools_info),
            ui_mode=agent.ui_mode
        )
        agent.logger.ulog("終了するには 'quit' または 'exit' を入力してください。", "info", always_print=True)
        
        # プロンプトセッション初期化
        agent._prompt_session = create_prompt_session(agent)
        
        agent.logger.ulog("-" * 60, "info", always_print=True)
        
        while True:
            try:
                if agent._prompt_session:
                    # prompt_toolkit使用
                    user_input = (await agent._prompt_session.prompt_async("Agent> ")).strip()
                elif agent._has_rich_method('input_prompt'):
                    user_input = agent.display.input_prompt("Agent").strip()
                else:
                    user_input = input("\nAgent> ").strip()
            except (EOFError, KeyboardInterrupt):
                # Ctrl+Cでも一時停止を実行
                if hasattr(agent, 'pause_session'):
                    agent.logger.ulog("\n作業を保存中...", "info", always_print=True)
                    await agent.pause_session()
                break
            
            if user_input.lower() in ['quit', 'exit', '終了']:
                break
            
            if not user_input:
                # 空行の場合：CLARIFICATION状態ならスキップ処理
                if agent.state_manager.has_pending_tasks():
                    pending_tasks = agent.state_manager.get_pending_tasks()
                    clarification_tasks = [t for t in pending_tasks if t.tool == "CLARIFICATION"]
                    
                    if clarification_tasks:
                        agent.logger.ulog("\n⏭ 確認をスキップします...", "info", always_print=True)
                        
                        # CLARIFICATIONをスキップして自動実行
                        clarification_task = clarification_tasks[0]  # 最初のCLARIFICATIONタスク
                        
                        # スマートクエリを生成して自動実行
                        smart_query = await agent.task_manager.handle_clarification_skip(
                            clarification_task, 
                            agent.conversation_manager,
                            agent.state_manager
                        )
                        
                        # 残りのCLARIFICATIONタスクもスキップ（複数ある場合）
                        for task in clarification_tasks[1:]:
                            await agent.task_manager.skip_clarification(task.task_id)
                        
                        agent.logger.ulog(f"\n自動実行中: {smart_query[:100]}...", "info", always_print=True)
                        
                        # スマートクエリで自動実行
                        from background_input_monitor import start_background_monitoring, stop_background_monitoring
                        from interrupt_manager import get_interrupt_manager
                        
                        # CLARIFICATION skip時は中断状態のみリセット
                        interrupt_manager = get_interrupt_manager()
                        interrupt_manager.reset_interrupt()
                        
                        try:
                            start_background_monitoring(verbose=True)
                            response = await agent.process_request(smart_query)
                        finally:
                            stop_background_monitoring()
                        
                        # Rich UIの場合はMarkdown整形表示
                        if agent._has_rich_method('show_markdown_result'):
                            agent.display.show_markdown_result(response)
                        else:
                            agent.logger.ulog(f"\n{response}", "info", always_print=True)
                        
                        continue
                
                # 通常時の空行は無視
                continue
            
            # コマンド処理をチェック
            if user_input.startswith("/"):
                command_result = await command_manager.process(user_input)
                if command_result:
                    # コマンド結果は通常の出力で表示
                    agent.logger.ulog(f"\n{command_result}", "info:command", always_print=True)
                    continue
            
            # 通常のリクエスト処理
            from background_input_monitor import start_background_monitoring, stop_background_monitoring
            from interrupt_manager import get_interrupt_manager
            
            # 新しいリクエスト開始時に中断状態をリセット
            interrupt_manager = get_interrupt_manager()
            interrupt_manager.reset_interrupt()
            
            # セッションクリアを削除 - 会話履歴とタスク状態を自然な流れで管理
            
            try:
                # 実行フェーズに入るので BG 監視を開始
                start_background_monitoring(verbose=True)  # 実行中の ESC を拾う
                response = await agent.process_request(user_input)
            finally:
                # REPL に戻る直前で必ず停止（競合防止）
                stop_background_monitoring()
            
            # Rich UIの場合はMarkdown整形表示
            if agent._has_rich_method('show_markdown_result'):
                agent.display.show_markdown_result(response)
            else:
                agent.logger.ulog(f"\n{response}", "info", always_print=True)
    
    except EscInterrupt:
        agent.logger.ulog("\n\nESCキーによる中断です。", "warning:interrupt", always_print=True)
    except KeyboardInterrupt:
        agent.logger.ulog("\n\nCtrl+Cが押されました。", "warning:interrupt", always_print=True)
    except Exception as e:
        agent.logger.ulog(f"\n\n予期しないエラー: {e}", "error", always_print=True)
    finally:
        try:
            await agent.close()
        except (asyncio.CancelledError, Exception):
            # クリーンアップエラーは無視
            pass
        agent.logger.ulog("\nMCP Agent を終了しました。", "info", always_print=True)


if __name__ == "__main__":
    asyncio.run(main())