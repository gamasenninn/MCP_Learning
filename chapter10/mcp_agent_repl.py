#!/usr/bin/env python3
"""
MCP Agent REPL Interface
対話的なコマンドラインインターフェース

主な機能:
- コマンドライン対話型インターフェース
- ESCキーによるスキップ/キャンセル機能
- Rich/Simple UI対応
- Ctrl+C割り込み処理
"""

import asyncio
from mcp_agent import MCPAgent
from repl_commands import CommandManager
from interrupt_manager import get_interrupt_manager
from task_executor import EscInterrupt

# prompt_toolkit support
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


def create_prompt_session(agent):
    """ESCでスキップ/キャンセル機能付きプロンプトセッション作成"""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    
    try:
        bindings = KeyBindings()
        
        # ESCキーのdebounce制御
        last_esc_time = [0.0]  # リストで包んで参照渡し
        
        @bindings.add('escape')  # ESC単発のみ
        async def handle_esc(event):
            try:
                import time
                
                current_time = time.monotonic()
                interrupt_manager = get_interrupt_manager()
                status = interrupt_manager.get_status()
                
                # ダブルESCは即確定（1.2秒以内の連打）
                if current_time - last_esc_time[0] < 1.2 and status['is_executing']:
                    interrupt_manager.request_interrupt()
                    interrupt_manager.confirm_interrupt()
                    agent.logger.ulog("\n[DOUBLE-ESC] 中断を確定しました", "warning:interrupt", always_print=True)
                    try:
                        event.app.exit(result='')
                    except Exception:
                        pass
                    return
                
                # debounce制御（0.2秒以内は無視）
                if current_time - last_esc_time[0] < 0.2:
                    return
                last_esc_time[0] = current_time
                
                # CLARIFICATION状態かチェック
                if agent.state_manager.has_pending_tasks():
                    pending_tasks = agent.state_manager.get_pending_tasks()
                    clarification_tasks = [t for t in pending_tasks if t.tool == "CLARIFICATION"]
                    
                    if clarification_tasks:
                        agent.logger.ulog("\n⏭ 確認をスキップします...", "info", always_print=True)
                        try:
                            event.app.exit(result='skip')
                        except Exception:
                            pass  # 既にexitされている場合を無視
                        return
                
                # 実行中のタスクがある場合は中断要求を発行
                status = interrupt_manager.get_status()
                if status['is_executing']:
                    interrupt_manager.request_interrupt()
                    agent.logger.ulog("\n[INTERRUPT] タスク中断要求を送信しました", "info:interrupt", always_print=True)
                    try:
                        event.app.exit(result='')
                    except Exception:
                        pass  # 既にexitされている場合を無視
                    return
                
                # 通常時は入力をキャンセル
                agent.logger.ulog("\n入力をキャンセルしました", "info:esc", always_print=True)
                try:
                    event.app.exit(result='')
                except Exception:
                    pass  # 既にexitされている場合を無視
                    
            except Exception as e:
                # すべての例外をキャッチして静かに処理
                try:
                    agent.logger.ulog(f"\nESC処理エラー: {e}", "debug", always_print=False)
                except:
                    pass
        
        return PromptSession(key_bindings=bindings)
    
    except Exception:
        # Windows環境やCI環境でのコンソールエラーを無視
        return None


async def main():
    """メイン実行関数"""
    print("MCP Agent を起動しています...")
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
        if agent._prompt_session:
            agent.logger.ulog("ESCキー: 確認スキップ/入力キャンセル", "info", always_print=True)
        
        agent.logger.ulog("-" * 60, "info", always_print=True)
        
        while True:
            try:
                if agent._prompt_session:
                    # prompt_toolkit使用
                    user_input = await agent._prompt_session.prompt_async("Agent> ")
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