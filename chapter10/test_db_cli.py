#!/usr/bin/env python3
"""
mcp_cli.pyを使ってdatabase_server.pyをテスト
"""

import subprocess
import sys

def run_command(cmd, description):
    """コマンドを実行して結果を表示"""
    print(f"\n{'='*60}")
    print(f"テスト: {description}")
    print(f"コマンド: {cmd}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("エラー:", result.stderr)
    
    return result.returncode == 0

def main():
    print("database_server.py CLIテスト")
    print("修正版：絶対パスでDBファイルを参照")
    
    tests = [
        (
            'uv run python mcp_cli.py --server C:\\MCP_Learning\\chapter06\\database_server.py --list',
            "chapter09からツール一覧を取得"
        ),
        (
            'uv run python mcp_cli.py --server C:\\MCP_Learning\\chapter06\\database_server.py --tool list_tables --args ""',
            "chapter09からテーブル一覧を取得"
        ),
        (
            'cd C:\\MCP_Learning && uv run python chapter09\\mcp_cli.py --server chapter06\\database_server.py --tool list_tables --args ""',
            "ルートディレクトリから実行"
        ),
    ]
    
    success_count = 0
    for cmd, desc in tests:
        if run_command(cmd, desc):
            success_count += 1
            print("[OK] 成功")
        else:
            print("[FAIL] 失敗")
    
    print(f"\n{'='*60}")
    print(f"結果: {success_count}/{len(tests)} テスト成功")
    
    if success_count == len(tests):
        print("[成功] すべてのテストが成功しました！")
        print("database_server.pyは任意のディレクトリから正常に動作します。")
    else:
        print("[警告] 一部のテストが失敗しました。")

if __name__ == "__main__":
    main()