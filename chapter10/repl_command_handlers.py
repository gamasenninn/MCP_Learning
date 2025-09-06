#!/usr/bin/env python3
"""
REPL Command Handlers for MCP Agent
REPLコマンドのハンドラー実装

各コマンドの具体的な処理を実装するモジュール
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from config_manager import ConfigManager


class ReplCommandHandlers:
    """REPLコマンドハンドラークラス"""
    
    def __init__(self, agent):
        """
        Args:
            agent: MCPAgentインスタンス
        """
        self.agent = agent
    
    # ========== セッション管理コマンド ==========
    
    async def cmd_help(self, args: str = "") -> str:
        """ヘルプコマンド - 利用可能なコマンド一覧を表示"""
        if args:
            # 特定のコマンドのヘルプ
            cmd_name = f"/{args}" if not args.startswith("/") else args
            if cmd_name in self.agent.command_manager.commands:
                cmd = self.agent.command_manager.commands[cmd_name]
                lines = [
                    f"コマンド: {cmd.name}",
                    f"説明: {cmd.description}",
                    f"使用方法: {cmd.usage}"
                ]
                if cmd.aliases:
                    lines.append(f"エイリアス: {', '.join(cmd.aliases)}")
                return "\n".join(lines)
            else:
                return f"コマンド '{args}' は見つかりませんでした。"
        
        # 全コマンドの一覧
        lines = [
            "=== MCP Agent REPL コマンド ===",
            ""
        ]
        
        for cmd_name, cmd in sorted(self.agent.command_manager.commands.items()):
            alias_str = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"  {cmd.name:<12}{alias_str:<15} - {cmd.description}")
        
        lines.extend([
            "",
            "使用方法: /help [command] で詳細ヘルプを表示",
            "例: /help status"
        ])
        
        return "\n".join(lines)
    
    async def cmd_status(self, args: str = "") -> str:
        """ステータスコマンド - 現在のセッション状態を表示"""
        try:
            # StateManagerから詳細な状態を取得
            status = self.agent.state_manager.get_session_status(
                task_manager=self.agent.task_manager,
                ui_mode=self.agent.ui_mode,
                verbose=self.agent.verbose
            )
            
            lines = [
                "=== セッション状態 ===",
                ""
            ]
            
            # セッション情報
            session_info = status.get("session", {})
            if session_info.get("status") == "no_session":
                lines.append("📌 セッション: 未初期化")
            else:
                lines.extend([
                    f"📌 セッション ID: {session_info.get('session_id', 'N/A')}",
                    f"⏰ 作成日時: {session_info.get('created_at', 'N/A')}",
                    f"💬 会話履歴: {session_info.get('conversation_entries', 0)}件",
                    f"🔄 実行タイプ: {session_info.get('execution_type', 'N/A')}"
                ])
            
            lines.append("")
            
            # タスク情報
            task_info = status.get("tasks", {})
            if task_info:
                lines.extend([
                    f"📋 全タスク数: {task_info.get('total_tasks', 0)}",
                    f"⏳ 保留中: {task_info.get('pending_tasks', 0)}",
                    f"✅ 完了済み: {task_info.get('completed_tasks', 0)}",
                    f"❓ 確認待ち: {task_info.get('clarification_tasks', 0)}"
                ])
            
            lines.append("")
            
            # システム情報
            lines.extend([
                f"🎨 UI モード: {status.get('ui_mode', 'N/A')}",
                f"🔍 詳細ログ: {'ON' if status.get('verbose') else 'OFF'}",
                f"🔧 接続サーバー: {len(self.agent.connection_manager.clients)}個",
                f"🛠️ 利用可能ツール: {len(self.agent.connection_manager.tools_info)}個"
            ])
            
            # 再開可能性
            if status.get("can_resume", False):
                lines.append("\n💡 未完了の作業があります。継続できます。")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"状態取得エラー: {str(e)}"
    
    async def cmd_clear(self, args: str = "") -> str:
        """クリアコマンド - 現在のセッションをクリア"""
        try:
            await self.agent.state_manager.clear_current_session()
            return "✨ セッションをクリアしました。新しいセッションで開始します。"
        except Exception as e:
            return f"セッションクリアエラー: {str(e)}"
    
    # ========== ツール・タスク管理コマンド ==========
    
    async def cmd_tools(self, args: str = "") -> str:
        """ツールコマンド - 利用可能なツール一覧を表示
        
        引数:
          -v, --verbose: 詳細表示（説明文を全文表示）
          デフォルト: コンパクト表示（説明文を30文字まで表示）
        """
        try:
            # 詳細モードフラグを確認
            verbose_mode = args.strip().lower() in ["-v", "--verbose"]
            
            tools_info = self.agent.connection_manager.tools_info
            clients = self.agent.connection_manager.clients
            
            mode_text = "詳細" if verbose_mode else "コンパクト"
            lines = [
                f"=== 利用可能なツール（{mode_text}表示） ===",
                f"接続サーバー数: {len(clients)}",
                f"総ツール数: {len(tools_info)}",
                ""
            ]
            
            if not tools_info:
                lines.append("⚠️ 利用可能なツールがありません。")
                return "\n".join(lines)
            
            # コンパクトモードの場合はヒント表示
            if not verbose_mode:
                lines.append("💡 詳細説明を見るには: /tools -v")
                lines.append("")
            
            # サーバー別にグループ化
            server_tools = {}
            for tool_name, tool_info in tools_info.items():
                server_name = tool_info.get('server', 'Unknown')
                if server_name not in server_tools:
                    server_tools[server_name] = []
                server_tools[server_name].append((tool_name, tool_info))
            
            for server_name, tools in server_tools.items():
                lines.append(f"📡 {server_name}:")
                for tool_name, tool_info in sorted(tools):
                    description = tool_info.get('description', '説明なし')
                    
                    # コンパクトモードでは説明を整形
                    if not verbose_mode:
                        # 改行文字があったらそれ以降を切り捨て
                        description = description.split('\n')[0].split('\r')[0]
                        
                        # 30文字を超えたら切り詰め
                        if len(description) > 30:
                            description = description[:27] + "..."
                    
                    lines.append(f"  🔧 {tool_name:<20} - {description}")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"ツール情報取得エラー: {str(e)}"
    
    async def cmd_tasks(self, args: str = "") -> str:
        """タスクコマンド - タスク一覧を表示"""
        try:
            filter_type = args.lower() if args else "all"
            
            pending_tasks = self.agent.state_manager.get_pending_tasks()
            completed_tasks = self.agent.state_manager.get_completed_tasks()
            
            lines = [
                "=== タスク一覧 ===",
                ""
            ]
            
            # 保留中タスク
            if filter_type in ["all", "pending"] and pending_tasks:
                lines.append("⏳ 保留中のタスク:")
                for i, task in enumerate(pending_tasks, 1):
                    status_icon = "❓" if task.tool == "CLARIFICATION" else "📋"
                    lines.append(f"  {i}. {status_icon} {task.description}")
                    lines.append(f"     ツール: {task.tool}")
                    if task.created_at:
                        created_time = task.created_at.split('T')[1][:8] if 'T' in task.created_at else task.created_at
                        lines.append(f"     作成時刻: {created_time}")
                lines.append("")
            
            # 完了済みタスク（最新5件）
            if filter_type in ["all", "completed"] and completed_tasks:
                lines.append("✅ 完了済みのタスク (最新5件):")
                recent_completed = completed_tasks[-5:] if len(completed_tasks) > 5 else completed_tasks
                for i, task in enumerate(reversed(recent_completed), 1):
                    success_icon = "✅" if not task.error else "❌"
                    lines.append(f"  {i}. {success_icon} {task.description}")
                    lines.append(f"     ツール: {task.tool}")
                    if task.updated_at:
                        updated_time = task.updated_at.split('T')[1][:8] if 'T' in task.updated_at else task.updated_at
                        lines.append(f"     完了時刻: {updated_time}")
                lines.append("")
            
            # 統計
            total_tasks = len(pending_tasks) + len(completed_tasks)
            clarifications = len([t for t in pending_tasks if t.tool == "CLARIFICATION"])
            
            lines.extend([
                "📊 統計:",
                f"  総タスク数: {total_tasks}",
                f"  保留中: {len(pending_tasks)} (確認待ち: {clarifications})",
                f"  完了済み: {len(completed_tasks)}"
            ])
            
            if not pending_tasks and not completed_tasks:
                lines.append("📝 タスクはありません。")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"タスク情報取得エラー: {str(e)}"
    
    # ========== 履歴・保存・読み込みコマンド ==========
    
    async def cmd_history(self, args: str = "") -> str:
        """履歴コマンド - 会話履歴を表示"""
        try:
            # 件数指定の解析
            try:
                count = int(args) if args.strip() else 10
                count = max(1, min(count, 100))  # 1-100の範囲に制限
            except ValueError:
                count = 10
            
            # StateManagerから会話履歴を取得
            conversation_context = self.agent.state_manager.get_conversation_context(count)
            
            if not conversation_context:
                return "📝 会話履歴がありません。"
            
            lines = [
                f"=== 会話履歴 (最新{len(conversation_context)}件) ===",
                ""
            ]
            
            for entry in conversation_context:
                # タイムスタンプの整形
                timestamp = entry.get('timestamp', '')
                if timestamp:
                    # ISO形式から時刻のみ抽出
                    time_str = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp
                else:
                    time_str = "N/A"
                
                # ロール表示
                role = "👤 User" if entry['role'] == "user" else "🤖 Assistant"
                
                # メッセージ内容（長すぎる場合は省略）
                content = entry.get('content', '')
                if len(content) > 150:
                    content = content[:147] + "..."
                
                lines.append(f"[{time_str}] {role}: {content}")
            
            lines.append("")
            lines.append(f"💡 `/history {count * 2}` でより多くの履歴を表示")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"履歴取得エラー: {str(e)}"
    
    
    async def cmd_save(self, args: str = "") -> str:
        """保存コマンド - セッションをファイルに保存"""
        try:
            # ファイル名の決定（表示責任）
            if args.strip():
                filename = args.strip()
                if not filename.endswith('.json'):
                    filename += '.json'
            else:
                # 自動生成ファイル名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"session_{timestamp}.json"
            
            # エクスポートディレクトリの準備（表示責任）
            export_dir = self.agent.state_manager.get_export_dir()
            file_path = export_dir / filename
            
            # セッションデータをStateManagerから取得（ビジネスロジック）
            session_data = self.agent.state_manager.export_session_data()
            
            # システム情報を追加（表示責任）
            session_data["system_info"] = {
                "ui_mode": self.agent.ui_mode,
                "verbose": self.agent.verbose,
                "tools_count": len(self.agent.connection_manager.tools_info),
                "servers_count": len(self.agent.connection_manager.clients)
            }
            
            # ファイル保存（表示責任）
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            # 表示用メッセージの生成（表示責任）
            stats = session_data["statistics"]
            return f"""✅ セッションを保存しました: {filename}
📊 保存内容:
  • 会話: {stats['total_conversations']}件
  • タスク: {stats['total_tasks']}個 (完了: {stats['completed_tasks']}, 保留: {stats['pending_tasks']})
  • ファイルサイズ: {file_path.stat().st_size:,}バイト
💾 保存場所: {file_path}"""
            
        except Exception as e:
            return f"❌ 保存エラー: {str(e)}"
    
    async def cmd_load(self, args: str = "") -> str:
        """読み込みコマンド - 保存されたセッションを読み込み"""
        try:
            export_dir = self.agent.state_manager.get_export_dir()
            
            if not args.strip():
                # ファイル一覧をStateManagerから取得（ビジネスロジック）
                sessions = self.agent.state_manager.list_saved_sessions(str(export_dir))
                if not sessions:
                    return "📁 保存されたセッションファイルがありません。\n💡 `/save` でセッションを保存できます。"
                
                # 表示フォーマット（表示責任）
                lines = ["=== 利用可能な保存ファイル ===", ""]
                
                for i, session in enumerate(sessions[:10], 1):  # 最新10件
                    mtime = datetime.fromtimestamp(session["modified"])
                    time_str = mtime.strftime("%m/%d %H:%M")
                    
                    lines.append(f"{i:2d}. {Path(session['filename']).stem} ({time_str})")
                    lines.append(f"     💬 {session['conversations']}件の会話, 📋 {session['tasks']}個のタスク")
                
                lines.extend([
                    "", "使用方法:",
                    "  `/load filename` - ファイル名で読み込み",
                    "  `/load 1` - 番号で読み込み"
                ])
                
                return "\n".join(lines)
            
            # ファイル指定の解決（表示責任）
            file_path = None
            sessions = self.agent.state_manager.list_saved_sessions(str(export_dir))
            
            if args.strip().isdigit():
                # インデックス指定
                index = int(args.strip())
                if 1 <= index <= len(sessions):
                    file_path = Path(sessions[index - 1]["filepath"])
                else:
                    return f"❌ インデックス {index} は範囲外です。1-{len(sessions)}を指定してください。"
            else:
                # ファイル名指定
                filename = args.strip()
                if not filename.endswith('.json'):
                    filename += '.json'
                file_path = export_dir / filename
                
                if not file_path.exists():
                    return f"❌ ファイルが見つかりません: {filename}\n💡 `/load` で利用可能なファイルを確認できます。"
            
            # ファイル読み込みとインポート（ビジネスロジック）
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # StateManagerにインポート（ビジネスロジック）
            success = await self.agent.state_manager.import_session_data(session_data, clear_current=False)
            
            if not success:
                return f"❌ セッションの復元に失敗しました: {file_path.name}"
            
            # 結果表示（表示責任）
            stats = session_data.get("statistics", {})
            metadata = session_data.get("metadata", {})
            
            return f"""✅ セッションを読み込みました: {file_path.name}
📊 復元内容:
  • 会話: {stats.get('total_conversations', 0)}件
  • タスク履歴: {stats.get('total_tasks', 0)}個
  • エクスポート日時: {metadata.get('exported_at', 'N/A')}
💡 `/history` で読み込まれた会話を確認できます"""
            
        except Exception as e:
            return f"❌ 読み込みエラー: {str(e)}"
    
    # ========== 設定管理コマンド ==========
    
    async def cmd_config(self, args: str = "") -> str:
        """設定コマンド - 設定の表示と変更"""
        try:
            parts = args.split(None, 1) if args else []
            
            if not parts:
                # 全設定を表示
                return self._display_all_configs()
            
            key_path = parts[0]
            
            if len(parts) == 1:
                # 特定の設定値を表示
                value = ConfigManager.get_config_value(self.agent.config, key_path)
                if value is None:
                    available_keys = ConfigManager.get_all_config_keys(self.agent.config)
                    similar_keys = [k for k in available_keys if key_path.lower() in k.lower()][:5]
                    result = f"❌ 設定キー '{key_path}' が見つかりません。"
                    if similar_keys:
                        result += f"\n\n💡 似ているキー:\n" + "\n".join(f"  • {k}" for k in similar_keys)
                    return result
                
                return f"🔧 {key_path}: {value} ({type(value).__name__})"
            
            else:
                # 設定値を変更
                new_value = parts[1]
                old_value = ConfigManager.get_config_value(self.agent.config, key_path)
                
                if old_value is None:
                    return f"❌ 設定キー '{key_path}' が見つかりません。"
                
                # 値を変更
                ConfigManager.update_config_value(self.agent.config, key_path, new_value)
                
                # 変更を関連コンポーネントに反映
                success = await self._apply_config_changes(key_path)
                
                # 結果メッセージを作成
                result = f"✅ 設定を変更しました:\n🔧 {key_path}: {old_value} → {new_value}"
                if success:
                    result += f"\n💾 config.yamlに保存しました"
                else:
                    result += f"\n⚠️ ファイル保存に失敗（メモリ上のみ有効）"
                
                return result
            
        except ValueError as e:
            return f"❌ 設定エラー: {str(e)}"
        except Exception as e:
            return f"❌ 予期しないエラー: {str(e)}"
    
    async def cmd_verbose(self, args: str = "") -> str:
        """詳細ログ切り替えコマンド"""
        try:
            current_verbose = self.agent.config.development.verbose
            
            if not args:
                # 現在の状態を表示
                status = "✅ ON" if current_verbose else "❌ OFF"
                return f"🔍 詳細ログ: {status}\n💡 切り替えるには: /verbose on または /verbose off"
            
            arg = args.lower()
            if arg in ['on', 'true', 'yes', '1']:
                new_value = True
            elif arg in ['off', 'false', 'no', '0']:
                new_value = False
            else:
                return f"❌ 無効な値: {args}\n💡 使用方法: /verbose [on|off]"
            
            # 設定を変更
            self.agent.config.development.verbose = new_value
            
            # Loggerに反映
            if hasattr(self.agent, 'logger'):
                self.agent.logger.verbose = new_value
            
            # 設定を自動保存
            saved = ConfigManager.save_config_to_file(self.agent.config)
            
            status = "✅ ON" if new_value else "❌ OFF"
            result = f"🔍 詳細ログを{status}に変更しました"
            if saved:
                result += f"\n💾 config.yamlに保存しました"
            else:
                result += f"\n⚠️ ファイル保存に失敗（メモリ上のみ有効）"
            
            return result
            
        except Exception as e:
            return f"❌ エラー: {str(e)}"
    
    async def cmd_ui(self, args: str = "") -> str:
        """UIモード切り替えコマンド"""
        try:
            current_mode = self.agent.config.display.ui_mode
            available_modes = ['basic', 'rich']
            
            if not args:
                # 現在のモードを表示
                return f"""🎨 現在のUIモード: {current_mode}
💡 利用可能なモード:
  • basic: シンプルなprint文ベース
  • rich: 美しいUI（richライブラリ使用）
  
🔧 変更するには: /ui [mode]"""
            
            new_mode = args.lower()
            if new_mode not in available_modes:
                return f"❌ 無効なUIモード: {args}\n💡 利用可能: {', '.join(available_modes)}"
            
            # 設定を変更
            old_mode = current_mode
            self.agent.config.display.ui_mode = new_mode
            
            # UIモード変更をDisplayManagerに反映（存在する場合）
            if hasattr(self.agent, 'display'):
                # 実際のDisplayManagerの再初期化は複雑なため、単純な通知のみ
                pass
            
            # 設定を自動保存
            saved = ConfigManager.save_config_to_file(self.agent.config)
            
            result = f"🎨 UIモードを変更しました: {old_mode} → {new_mode}"
            if saved:
                result += f"\n💾 config.yamlに保存しました"
            else:
                result += f"\n⚠️ ファイル保存に失敗（メモリ上のみ有効）"
            result += f"\n⚠️ 一部の変更は再起動後に反映されます"
            
            return result
            
        except Exception as e:
            return f"❌ エラー: {str(e)}"
    
    # ========== ユーティリティメソッド ==========
    
    def _display_all_configs(self) -> str:
        """全設定を階層表示"""
        lines = ["=== 現在の設定 ===", ""]
        
        config_sections = [
            ("表示設定", self.agent.config.display),
            ("実行設定", self.agent.config.execution),  
            ("LLM設定", self.agent.config.llm),
            ("会話設定", self.agent.config.conversation),
            ("エラー処理", self.agent.config.error_handling),
            ("開発設定", self.agent.config.development),
            ("結果表示", self.agent.config.result_display)
        ]
        
        for section_name, section_config in config_sections:
            lines.append(f"📂 {section_name}:")
            for attr_name in dir(section_config):
                if not attr_name.startswith('_'):
                    value = getattr(section_config, attr_name)
                    # ネストしたオブジェクトの場合
                    if hasattr(value, '__dataclass_fields__'):
                        lines.append(f"  📁 {attr_name}:")
                        for nested_attr in dir(value):
                            if not nested_attr.startswith('_'):
                                nested_value = getattr(value, nested_attr)
                                lines.append(f"    🔧 {attr_name}.{nested_attr}: {nested_value}")
                    else:
                        lines.append(f"  🔧 {attr_name}: {value}")
            lines.append("")
        
        lines.extend([
            "💡 使用方法:",
            "  /config key value  - 設定を変更",
            "  /config key        - 特定の設定を表示", 
            "  /verbose [on|off]  - 詳細ログ切り替え",
            "  /ui [mode]         - UIモード切り替え"
        ])
        
        return "\n".join(lines)
    
    async def _apply_config_changes(self, key_path: str) -> bool:
        """設定変更を関連コンポーネントに反映"""
        try:
            # verboseの変更をLoggerに反映
            if key_path == 'development.verbose':
                if hasattr(self.agent, 'logger'):
                    self.agent.logger.verbose = self.agent.config.development.verbose
            
            # ui_modeの変更（再起動が必要な旨を通知済み）
            elif key_path == 'display.ui_mode':
                pass
            
            # その他の設定変更も必要に応じて追加
            
            # 設定をファイルに自動保存
            return ConfigManager.save_config_to_file(self.agent.config)
            
        except Exception as e:
            # 反映エラーは警告のみで処理を継続
            return False