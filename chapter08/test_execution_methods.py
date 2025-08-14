#!/usr/bin/env python3
"""
コード実行方法の比較テスト
- ファイル方式 vs 標準入力方式のパフォーマンス比較
"""

import subprocess
import sys
import tempfile
import os
import time
from typing import Dict, Any, Tuple

def execute_via_file(code: str, timeout: float = 5.0) -> Tuple[float, Dict[str, Any]]:
    """ファイル経由でコード実行（従来の方法）"""
    start_time = time.time()
    
    try:
        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
        
        # ファイルを実行
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        
        return elapsed, {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'method': 'file'
        }
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return elapsed, {
            'success': False,
            'error': f'タイムアウト（{timeout}秒）',
            'method': 'file'
        }
    finally:
        # 一時ファイルを削除
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.unlink(temp_file)


def execute_via_stdin_simple(code: str, timeout: float = 5.0) -> Tuple[float, Dict[str, Any]]:
    """標準入力経由でコード実行（シンプル版）"""
    start_time = time.time()
    
    try:
        # コードを標準入力経由で渡す
        result = subprocess.run(
            [sys.executable, "-c", "import sys; exec(sys.stdin.read())"],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
        )
        
        elapsed = time.time() - start_time
        
        return elapsed, {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'method': 'stdin_simple'
        }
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return elapsed, {
            'success': False,
            'error': f'タイムアウト（{timeout}秒）',
            'method': 'stdin_simple'
        }


def execute_via_stdin_isolated(code: str, timeout: float = 5.0) -> Tuple[float, Dict[str, Any]]:
    """標準入力経由でコード実行（隔離オプション付き）"""
    start_time = time.time()
    
    try:
        # 隔離オプション付きで実行
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", "import sys; exec(sys.stdin.read())"],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
        )
        
        elapsed = time.time() - start_time
        
        return elapsed, {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'method': 'stdin_isolated'
        }
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return elapsed, {
            'success': False,
            'error': f'タイムアウト（{timeout}秒）',
            'method': 'stdin_isolated'
        }


def run_tests():
    """各実行方法をテスト"""
    
    # テストケース
    test_cases = [
        ("簡単な計算", "print(1 + 2)"),
        ("ループ処理", """
for i in range(5):
    print(f'Count: {i}')
"""),
        ("関数定義と実行", """
def greet(name):
    return f'Hello, {name}!'

print(greet('World'))
"""),
        ("日本語出力", "print('こんにちは、世界！')"),
        ("複数行の計算", """
import math
radius = 5
area = math.pi * radius ** 2
print(f'円の面積: {area:.2f}')
"""),
    ]
    
    print("=" * 80)
    print("コード実行方法の比較テスト")
    print("=" * 80)
    
    # 各テストケースを実行
    for test_name, code in test_cases:
        print(f"\n### テスト: {test_name}")
        print(f"コード:\n{code}")
        print("-" * 40)
        
        # 方法1: ファイル経由
        time1, result1 = execute_via_file(code)
        print(f"\n1. ファイル経由:")
        print(f"   実行時間: {time1:.3f}秒")
        if result1['success']:
            print(f"   結果: {result1['stdout'].strip()}")
        else:
            print(f"   エラー: {result1.get('error', result1.get('stderr', 'Unknown error'))}")
        
        # 方法2: 標準入力（シンプル）
        time2, result2 = execute_via_stdin_simple(code)
        print(f"\n2. 標準入力（シンプル）:")
        print(f"   実行時間: {time2:.3f}秒")
        if result2['success']:
            print(f"   結果: {result2['stdout'].strip()}")
        else:
            print(f"   エラー: {result2.get('error', result2.get('stderr', 'Unknown error'))}")
        
        # 方法3: 標準入力（隔離）
        time3, result3 = execute_via_stdin_isolated(code)
        print(f"\n3. 標準入力（隔離）:")
        print(f"   実行時間: {time3:.3f}秒")
        if result3['success']:
            print(f"   結果: {result3['stdout'].strip()}")
        else:
            print(f"   エラー: {result3.get('error', result3.get('stderr', 'Unknown error'))}")
        
        # 性能比較
        print(f"\n速度比較:")
        print(f"   ファイル方式を1.0とした場合:")
        print(f"   - 標準入力（シンプル）: {time2/time1:.2f}倍")
        print(f"   - 標準入力（隔離）: {time3/time1:.2f}倍")
    
    # パフォーマンステスト
    print("\n" + "=" * 80)
    print("パフォーマンステスト（100回実行）")
    print("=" * 80)
    
    simple_code = "print('Hello, World!')"
    iterations = 100
    
    # ファイル方式
    start = time.time()
    for _ in range(iterations):
        execute_via_file(simple_code)
    file_total = time.time() - start
    
    # 標準入力（シンプル）
    start = time.time()
    for _ in range(iterations):
        execute_via_stdin_simple(simple_code)
    stdin_simple_total = time.time() - start
    
    # 標準入力（隔離）
    start = time.time()
    for _ in range(iterations):
        execute_via_stdin_isolated(simple_code)
    stdin_isolated_total = time.time() - start
    
    print(f"\n{iterations}回実行の合計時間:")
    print(f"1. ファイル方式: {file_total:.2f}秒 (平均: {file_total/iterations:.3f}秒)")
    print(f"2. 標準入力（シンプル）: {stdin_simple_total:.2f}秒 (平均: {stdin_simple_total/iterations:.3f}秒)")
    print(f"3. 標準入力（隔離）: {stdin_isolated_total:.2f}秒 (平均: {stdin_isolated_total/iterations:.3f}秒)")
    
    print(f"\nパフォーマンス改善:")
    print(f"- 標準入力（シンプル）: {file_total/stdin_simple_total:.1f}倍高速")
    print(f"- 標準入力（隔離）: {file_total/stdin_isolated_total:.1f}倍高速")


if __name__ == "__main__":
    print("注意: このテストはWindows環境で特に顕著な差が出ます。")
    print("ウイルス対策ソフトが有効な場合、ファイル方式は更に遅くなる可能性があります。\n")
    
    run_tests()