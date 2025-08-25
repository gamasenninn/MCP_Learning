#!/usr/bin/env python3
"""
Test Japanese Hanoi Tower code with different surrogate policies
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from connection_manager import ConnectionManager

async def test_japanese_hanoi_with_policy(policy: str):
    """Test with Japanese Hanoi Tower code using specific policy"""
    
    # Japanese Hanoi Tower code with Japanese strings
    japanese_hanoi_code = """
def hanoi(n, source, target, auxiliary):
    if n == 1:
        print(f'円盤 1 を {source} から {target} へ移動')
        return
    hanoi(n - 1, source, auxiliary, target)
    print(f'円盤 {n} を {source} から {target} へ移動')
    hanoi(n - 1, auxiliary, target, source)

print('ハノイの塔の解法を開始します...')
hanoi(3, 'A', 'C', 'B')
print('完了しました！')
"""
    
    print(f"=== Testing Japanese Code with SURROGATE_POLICY={policy} ===")
    
    # Set environment variable
    os.environ["SURROGATE_POLICY"] = policy
    
    try:
        # Initialize connection manager
        cm = ConnectionManager("mcp_servers.json", verbose=False)
        await cm.initialize()
        
        print(f"Executing Japanese Hanoi Tower code with policy: {policy}")
        result = await cm.call_tool("execute_python", {"code": japanese_hanoi_code})
        
        print(f"Result type: {type(result)}")
        if hasattr(result, 'content') and result.content:
            print(f"Result content: {result.content[0].text}")
        else:
            print(f"Result: {result}")
        
        await cm.close()
        print(f"Test with policy '{policy}' completed successfully!")
        return True
        
    except Exception as e:
        print(f"Test with policy '{policy}' failed with error: {e}")
        # Check for surrogate characters in error
        error_str = str(e)
        surrogate_count = sum(1 for char in error_str if 0xD800 <= ord(char) <= 0xDFFF)
        print(f"Surrogate characters in error: {surrogate_count}")
        return False

async def main():
    """Test all surrogate policies"""
    policies = ["replace", "ignore", "escape"]
    
    results = {}
    for policy in policies:
        print()
        success = await test_japanese_hanoi_with_policy(policy)
        results[policy] = success
        print("-" * 50)
    
    print("\n=== Summary ===")
    for policy, success in results.items():
        status = "SUCCESS" if success else "FAILED"
        print(f"{policy:10}: {status}")

if __name__ == "__main__":
    asyncio.run(main())