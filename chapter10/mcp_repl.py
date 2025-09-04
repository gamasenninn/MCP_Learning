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
        
        @bindings.add('escape')  # ESC単発のみ
        async def handle_esc(event):
            # CLARIFICATION状態かチェック
            if agent.state_manager.has_pending_tasks():
                pending_tasks = agent.state_manager.get_pending_tasks()
                clarification_tasks = [t for t in pending_tasks if t.tool == "CLARIFICATION"]
                
                if clarification_tasks:
                    agent.logger.ulog("\n⏭ 確認をスキップします...", "info", always_print=True)
                    event.app.exit(result='skip')
                    return
            
            # 通常時は入力をキャンセル
            agent.logger.ulog("\n入力をキャンセルしました", "info:esc", always_print=True)
            event.app.exit(result='')
        
        return PromptSession(key_bindings=bindings)
    
    except Exception:
        # Windows環境やCI環境でのコンソールエラーを無視
        return None


async def main():
    """メイン実行関数"""
    print("MCP Agent を起動しています...")
    agent = MCPAgent()
    await agent.initialize()
    
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
            
            # リクエスト処理
            response = await agent.process_request(user_input)
            
            # Rich UIの場合はMarkdown整形表示
            if agent._has_rich_method('show_markdown_result'):
                agent.display.show_markdown_result(response)
            else:
                agent.logger.ulog(f"\n{response}", "info", always_print=True)
    
    except KeyboardInterrupt:
        agent.logger.ulog("\n\nCtrl+Cが押されました。", "warning:interrupt", always_print=True)
    finally:
        try:
            await agent.close()
        except (asyncio.CancelledError, Exception):
            # クリーンアップエラーは無視
            pass
        agent.logger.ulog("\nMCP Agent を終了しました。", "info", always_print=True)


if __name__ == "__main__":
    asyncio.run(main())