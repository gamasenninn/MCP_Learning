#!/usr/bin/env python3
"""
FastMCPを使った実用的なCLIクライアント
コマンドラインから簡単にツールを実行
"""

import argparse
import asyncio
import json
import shlex
import sys
from pathlib import Path
from fastmcp import Client

def extract_text(result):
    """結果からテキストを抽出"""
    sc = getattr(result, "structured_content", None)
    if isinstance(sc, dict) and "result" in sc:
        return str(sc["result"])
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        first = content[0]
        txt = getattr(first, "text", None)
        if isinstance(txt, str):
            return txt
    data = getattr(result, "data", None)
    if data is not None:
        return str(data)
    return str(result)

def parse_tool_args(args_string):
    """ツール引数をパース（改善版）"""
    tool_args = {}
    
    if not args_string:
        return tool_args
    
    # JSON形式の場合
    if args_string.strip().startswith('{'):
        try:
            return json.loads(args_string)
        except json.JSONDecodeError:
            pass
    
    # key=value形式の場合（shlexでパース）
    try:
        # Windows環境を考慮したパース
        if sys.platform == "win32":
            # Windowsの場合は直接分割
            parts = args_string.split()
        else:
            # Unix系の場合はshlexを使用
            parts = shlex.split(args_string)
        
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                # 引用符を削除
                value = value.strip('"').strip("'")
                # 数値に変換を試みる
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    # 文字列として保持
                    pass
                tool_args[key] = value
    except Exception as e:
        print(f"⚠️ 引数のパースに失敗: {e}", file=sys.stderr)
        print(f"  入力: {args_string}", file=sys.stderr)
    
    return tool_args

async def main():
    parser = argparse.ArgumentParser(
        description="FastMCP CLI Client",
        epilog="""
使用例:
  # ツール一覧を表示
  %(prog)s --server server.py --list
  
  # 計算を実行
  %(prog)s --server calc.py --tool add --args "a=100 b=200"
  
  # コードを実行（JSON形式）
  %(prog)s --server exec.py --tool execute_python --args '{"code": "print(42)"}'
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--server", required=True, help="サーバーのパス")
    parser.add_argument("--tool", help="実行するツール名")
    parser.add_argument("--args", default="", help="ツールの引数 (key=value形式またはJSON)")
    parser.add_argument("--list", action="store_true", help="ツール一覧を表示")
    
    args = parser.parse_args()
    
    # --listが指定されていない場合は--toolが必須
    if not args.list and not args.tool:
        parser.error("--tool is required unless --list is specified")
    
    # 引数をパース
    tool_args = parse_tool_args(args.args)
    
    # クライアントを作成
    try:
        # サーバーファイルの存在確認
        server_path = Path(args.server)
        if not server_path.exists():
            print(f"❌ サーバーファイルが見つかりません: {args.server}", file=sys.stderr)
            return 1
        
        # FastMCPのClientは直接ファイルパスを受け取る
        client = Client(str(server_path.absolute()))
        
        async with client:
            await client.ping()
            
            if args.list:
                # ツール一覧を表示
                tools = await client.list_tools()
                print("📋 利用可能なツール:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description}")
            else:
                # ツールを実行
                print(f"🚀 {args.tool} を実行中...")
                print(f"   引数: {tool_args}")
                try:
                    result = await client.call_tool(args.tool, tool_args)
                    print(f"✅ 結果: {extract_text(result)}")
                except Exception as e:
                    print(f"❌ ツール実行エラー: {e}", file=sys.stderr)
                    return 1
    
    except Exception as e:
        print(f"❌ 接続エラー: {e}", file=sys.stderr)
        print("\n💡 ヒント:", file=sys.stderr)
        print("  - サーバーファイルのパスが正しいか確認してください", file=sys.stderr)
        print("  - サーバーが正常に起動できるか確認してください", file=sys.stderr)
        print(f"  - 指定されたパス: {args.server}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))