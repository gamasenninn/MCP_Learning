#!/usr/bin/env python3
"""
統合MCPエージェント実行スクリプト
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

def print_banner():
    """バナーを表示"""
    print("\n" + "=" * 70)
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║      統合MCPエージェント - Integrated MCP Agent         ║
    ║                                                          ║
    ║  AIによる自動タスク分解・実行・エラー回復を実現         ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    print("=" * 70)

async def quick_demo():
    """クイックデモ"""
    print("\n[クイックデモモード]")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=True
    )
    
    await agent.initialize()
    
    # デモクエリ
    demo_queries = [
        "100と200を足して",
        "2の10乗を計算して",
        "1000から350を引いて、その結果を2で割って"
    ]
    
    print("\n以下のタスクを実行します:")
    for i, query in enumerate(demo_queries, 1):
        print(f"  {i}. {query}")
    
    print("\n実行を開始します...")
    print("-" * 40)
    
    for query in demo_queries:
        result = await agent.process_request(query, interpret_result=True)
        print("")  # 空行を入れて見やすくする
    
    await agent.cleanup()
    print("\nデモを終了しました")

async def batch_mode(queries: list, interpret: bool = True):
    """バッチ実行モード"""
    print("\n[バッチ実行モード]")
    print(f"  {len(queries)}個のタスクを実行します")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False  # バッチモードでは簡潔な出力
    )
    
    await agent.initialize()
    
    results = []
    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] {query}")
        result = await agent.process_request(query, interpret_result=interpret)
        
        if result["success"]:
            if interpret and "interpretation" in result:
                print(f"  → {result['interpretation']}")
            else:
                print(f"  → 成功: {result['result']}")
        else:
            print(f"  → 失敗: {result['error']}")
        
        results.append(result)
    
    # 統計を表示
    success_count = sum(1 for r in results if r["success"])
    print("\n" + "=" * 40)
    print(f"実行結果: {success_count}/{len(queries)} 成功")
    
    await agent.cleanup()

async def interactive_mode(session_file: str = None):
    """対話モード"""
    print_banner()
    
    # 設定の確認
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("✓ OpenAI API設定済み - AI機能が利用可能です")
    else:
        print("⚠ OpenAI API未設定 - 基本機能のみ利用可能です")
    
    # エージェントの作成
    agent = IntegratedMCPAgent(
        use_ai=bool(api_key),
        enable_learning=True,
        verbose=True
    )
    
    try:
        # 初期化
        await agent.initialize()
        
        # セッションファイルがあれば読み込み
        if session_file and Path(session_file).exists():
            if agent.load_session(session_file):
                print(f"✓ セッション復元: {session_file}")
        
        # 対話セッション開始
        await agent.interactive_session()
        
    finally:
        # セッションの保存
        if session_file:
            agent.save_session(session_file)
            print(f"✓ セッション保存: {session_file}")
        else:
            # デフォルトファイルに保存
            agent.save_session()
        
        # クリーンアップ
        await agent.cleanup()

async def execute_file(file_path: str):
    """ファイルからタスクを読み込んで実行"""
    if not Path(file_path).exists():
        print(f"エラー: ファイル {file_path} が見つかりません")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if not queries:
        print("エラー: 実行するタスクがありません")
        return
    
    print(f"\n[ファイル実行モード] {file_path}")
    await batch_mode(queries)

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="統合MCPエージェント - 自然言語でMCPツールを操作",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 対話モード（デフォルト）
  python run_integrated_agent.py
  
  # クイックデモ
  python run_integrated_agent.py --demo
  
  # バッチ実行
  python run_integrated_agent.py --batch "100と200を足して" "2の8乗を計算"
  
  # ファイルから実行
  python run_integrated_agent.py --file tasks.txt
  
  # セッション復元
  python run_integrated_agent.py --session my_session.json
        """
    )
    
    parser.add_argument(
        '--demo', 
        action='store_true',
        help='クイックデモを実行'
    )
    
    parser.add_argument(
        '--batch',
        nargs='+',
        metavar='QUERY',
        help='バッチモードで実行するクエリ'
    )
    
    parser.add_argument(
        '--file',
        metavar='FILE',
        help='タスクファイルから実行'
    )
    
    parser.add_argument(
        '--session',
        metavar='FILE',
        help='セッションファイル（保存/復元）'
    )
    
    parser.add_argument(
        '--no-ai',
        action='store_true',
        help='AI機能を無効化'
    )
    
    parser.add_argument(
        '--no-interpret',
        action='store_true',
        help='結果の解釈機能を無効化'
    )
    
    args = parser.parse_args()
    
    # AI機能の制御
    if args.no_ai:
        os.environ.pop("OPENAI_API_KEY", None)
    
    # 結果解釈フラグ
    interpret = not args.no_interpret
    
    # モード選択
    if args.demo:
        asyncio.run(quick_demo())
    elif args.batch:
        asyncio.run(batch_mode(args.batch, interpret=interpret))
    elif args.file:
        asyncio.run(execute_file(args.file))
    else:
        # デフォルト: 対話モード
        asyncio.run(interactive_mode(args.session))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n中断されました")
        sys.exit(0)
    except Exception as e:
        print(f"\nエラー: {e}")
        sys.exit(1)