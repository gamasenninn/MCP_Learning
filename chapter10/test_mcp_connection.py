"""
MCPサーバー接続テスト
FastMCPサーバーとの通信を確認
"""

import subprocess
import sys
from pathlib import Path

def test_server_direct(server_path):
    """サーバーを直接起動してテスト"""
    print(f"\nTesting: {server_path}")
    print("-" * 40)
    
    if not Path(server_path).exists():
        print(f"[ERROR] File not found: {server_path}")
        return False
    
    try:
        # サーバーを直接起動（ヘルプ表示）
        result = subprocess.run(
            ["uv", "run", "python", server_path, "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(server_path).parent),
            timeout=5
        )
        
        if result.returncode == 0:
            print("[OK] Server can be executed")
            print(f"Output: {result.stdout[:200]}...")
            return True
        else:
            print(f"[ERROR] Exit code: {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("[ERROR] Timeout - server took too long to respond")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def main():
    """メイン処理"""
    print("MCP Server Connection Test")
    print("=" * 60)
    
    servers = [
        ("Calculator", "C:\\MCP_Learning\\chapter03\\calculator_server.py"),
        ("Database", "C:\\MCP_Learning\\chapter06\\database_server.py"),
        ("Weather", "C:\\MCP_Learning\\chapter07\\external_api_server.py"),
        ("Universal", "C:\\MCP_Learning\\chapter08\\universal_tools_server.py")
    ]
    
    results = []
    for name, path in servers:
        print(f"\n{name} Server:")
        success = test_server_direct(path)
        results.append((name, success))
    
    print("\n" + "=" * 60)
    print("Summary:")
    for name, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    print("\nNote: MCPサーバーはClaude Desktop経由での使用を想定しています。")
    print("      エージェントからの直接接続には追加の実装が必要です。")
    print("\nRecommendation: まずはモックモードで動作を確認してください。")
    print("  uv run python examples\\simple_demo.py")

if __name__ == "__main__":
    main()