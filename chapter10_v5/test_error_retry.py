#!/usr/bin/env python3
"""
Test script for error retry functionality
"""

import asyncio
import sys
import os

# Ensure the current directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_agent import MCPAgent

async def test_fibonacci_error_retry():
    """Test the Fibonacci sequence generation with error retry"""
    
    print("Testing Fibonacci error retry functionality...")
    print("=" * 60)
    
    # Create agent instance
    agent = MCPAgent()
    
    # Initialize the agent
    await agent.initialize()
    
    print("\n[Testing] Fibonacci sequence generation with intentional error...")
    
    # Test with a query that should trigger syntax error and retry
    query = "フィボナッチ数列の最初の10個の数を出力してください"
    
    try:
        # Use the internal method to execute
        result = await agent._execute_dialogue(query)
        print("\n[Result]")
        print(result)
    except Exception as e:
        print(f"\n[Error] {e}")
    finally:
        # Cleanup
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(test_fibonacci_error_retry())