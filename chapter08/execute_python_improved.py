#!/usr/bin/env python3
"""
改善されたPython実行関数（標準入力方式・日本語対応）
"""

from fastmcp import FastMCP
import subprocess
import sys
import os
import tempfile
from typing import Dict, Any

mcp = FastMCP("Improved Execution Server")

@mcp.tool()
def execute_python_file_based(code: str) -> Dict[str, Any]:
    """
    従来のファイルベース実行（比較用）
    """
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
        
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8'  # 日本語対応
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'method': 'file-based'
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'タイムアウト（5秒）',
            'method': 'file-based'
        }
    finally:
        if 'temp_file' in locals():
            import os
            os.unlink(temp_file)


@mcp.tool()
def execute_python_stdin_improved(code: str) -> Dict[str, Any]:
    """
    改善版：標準入力経由でコード実行（日本語対応）
    """
    try:
        # 環境変数でPythonのエンコーディングを指定
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(
            [sys.executable, "-c", "import sys; exec(sys.stdin.read())"],
            input=code,
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            env=env  # 環境変数を渡す
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'method': 'stdin-improved'
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'タイムアウト（5秒）',
            'method': 'stdin-improved'
        }


@mcp.tool()
def execute_python_stdin_isolated(code: str) -> Dict[str, Any]:
    """
    標準入力経由・隔離版（日本語対応）
    """
    try:
        # Windowsでの日本語対応
        import os
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 一時ディレクトリで実行
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-c", 
                 "import sys; exec(sys.stdin.read())"],
                input=code,
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                cwd=tmpdir,
                env=env
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'method': 'stdin-isolated'
            }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'タイムアウト（5秒）',
            'method': 'stdin-isolated'
        }


def test_functions():
    """各実行方法をテスト"""
    import time
    
    test_code = """
print('こんにちは、世界！')
print('Hello, World!')
for i in range(3):
    print(f'カウント: {i}')
"""
    
    print("=" * 60)
    print("実行方法の比較テスト（日本語対応版）")
    print("=" * 60)
    print(f"\nテストコード:\n{test_code}")
    print("-" * 60)
    
    # ファイルベース
    print("\n1. ファイルベース実行:")
    start = time.time()
    result = execute_python_file_based(test_code)
    elapsed = time.time() - start
    print(f"   実行時間: {elapsed:.3f}秒")
    if result['success']:
        print(f"   出力:\n{result['stdout']}")
    else:
        print(f"   エラー: {result.get('error', result['stderr'])}")
    
    # 標準入力（改善版）
    print("\n2. 標準入力実行（改善版）:")
    start = time.time()
    result = execute_python_stdin_improved(test_code)
    elapsed = time.time() - start
    print(f"   実行時間: {elapsed:.3f}秒")
    if result['success']:
        print(f"   出力:\n{result['stdout']}")
    else:
        print(f"   エラー: {result.get('error', result['stderr'])}")
    
    # 標準入力（隔離版）
    print("\n3. 標準入力実行（隔離版）:")
    start = time.time()
    result = execute_python_stdin_isolated(test_code)
    elapsed = time.time() - start
    print(f"   実行時間: {elapsed:.3f}秒")
    if result['success']:
        print(f"   出力:\n{result['stdout']}")
    else:
        print(f"   エラー: {result.get('error', result['stderr'])}")


if __name__ == "__main__":
    import os
    test_functions()
    
    # MCPサーバーとして起動する場合
    # mcp.run()