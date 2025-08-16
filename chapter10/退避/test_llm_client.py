"""
LLMクライアントのテスト
"""

import asyncio
from llm_client import get_llm_client

async def test_basic():
    """基本的なテスト"""
    client = get_llm_client()
    
    # シンプルなテスト
    print("Test 1: Simple greeting")
    result = await client.complete("Say hello in Japanese")
    print(f"Response: {result.content}")
    if result.usage:
        print(f"Tokens: {result.usage.get('total_tokens', 'N/A')}")
    print()
    
    # システムプロンプト付き
    print("Test 2: With system prompt")
    result = await client.complete(
        "What is 10 + 20?",
        system="You are a helpful math teacher. Answer concisely."
    )
    print(f"Response: {result.content}")
    print()
    
    # 温度設定
    print("Test 3: Creative response (high temperature)")
    result = await client.complete(
        "Write a one-line poem about coding",
        temperature=0.9
    )
    print(f"Response: {result.content}")

async def test_error_handling():
    """エラーハンドリングのテスト"""
    print("\nTest 4: Error handling")
    
    # APIキーなしでテスト（エラーになるはず）
    import os
    original_key = os.environ.get("OPENAI_API_KEY")
    
    try:
        # 一時的に無効なキーを設定
        os.environ["OPENAI_API_KEY"] = "invalid-key"
        client = get_llm_client()
        result = await client.complete("Hello")
        print(f"Response: {result.content if result else 'No response'}")
    except Exception as e:
        print(f"Error caught: {e}")
    finally:
        # 元のキーを復元
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key

if __name__ == "__main__":
    print("LLM Client Test")
    print("="*50)
    
    asyncio.run(test_basic())
    asyncio.run(test_error_handling())