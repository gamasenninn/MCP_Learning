#!/usr/bin/env python3
"""
FastMCPを使った実用的なCLIクライアント
コマンドラインから簡単にツールを実行
"""

import argparse
import asyncio
import json
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

async def main():
    parser = argparse.ArgumentParser(description="FastMCP CLI Client")
    parser.add_argument("--server", required=True, help="サーバーのパス")
    parser.add_argument("--tool", help="実行するツール名")
    parser.add_argument("--args", nargs="*", default=[], help="ツールの引数 (key=value形式)")
    parser.add_argument("--list", action="store_true", help="ツール一覧を表示")
    
    args = parser.parse_args()
    
    # --listが指定されていない場合は--toolが必須
    if not args.list and not args.tool:
        parser.error("--tool is required unless --list is specified")
    
    # 引数をパース
    tool_args = {}
    for arg in args.args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            # 数値に変換を試みる
            try:
                value = float(value)
                if value.is_integer():
                    value = int(value)
            except ValueError:
                pass
            tool_args[key] = value
    
    # クライアントを作成
    client = Client(args.server)
    
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
            result = await client.call_tool(args.tool, tool_args)
            print(f"✅ 結果: {extract_text(result)}")

if __name__ == "__main__":
    asyncio.run(main())