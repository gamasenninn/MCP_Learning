#!/usr/bin/env python3
"""
サーバーのインポートをテスト
"""

import sys
import traceback
from pathlib import Path

def test_server_imports(server_path):
    """サーバーファイルのインポートをテスト"""
    print(f"\n=== {server_path} のインポートテスト ===")
    
    try:
        # ファイルを読み込んで実行
        with open(server_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # コンパイルして確認
        compile(code, server_path, 'exec')
        print("✅ 構文エラーなし")
        
        # 必要なモジュールを確認
        import ast
        tree = ast.parse(code)
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    if module:
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)
        
        print(f"📦 必要なモジュール: {', '.join(set(imports))}")
        
        # 実際にインポートを試す
        for imp in set(imports):
            try:
                if '.' in imp:
                    module = imp.split('.')[0]
                    __import__(module)
                else:
                    __import__(imp)
            except ImportError as e:
                print(f"❌ インポートエラー: {imp} - {e}")
                return False
        
        print("✅ すべてのモジュールが利用可能")
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # テストするサーバー
    servers = [
        r"C:\MCP_Learning\chapter03\calculator_server.py",
        r"C:\MCP_Learning\chapter08\universal_tools_server.py"
    ]
    
    for server in servers:
        if Path(server).exists():
            test_server_imports(server)
        else:
            print(f"❌ ファイルが存在しません: {server}")