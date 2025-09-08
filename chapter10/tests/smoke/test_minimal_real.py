#!/usr/bin/env python3
"""
Smoke tests for minimal real environment verification
最小限のリアル環境動作確認用スモークテスト
"""

import pytest
import os
from unittest.mock import patch


@pytest.mark.smoke
@pytest.mark.real
def test_api_key_available():
    """API KEYが利用可能か確認"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "test_key":
        pytest.skip("No real API key available (this is expected for mock tests)")
    
    assert len(api_key) > 20, "API key seems too short"
    assert api_key.startswith("sk-"), "API key should start with 'sk-'"


@pytest.mark.smoke
@pytest.mark.real
@pytest.mark.asyncio
async def test_llm_connection(real_llm_client):
    """LLM APIへの接続確認"""
    try:
        # 最小限のAPI呼び出し
        response = await real_llm_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'OK' if you can read this"}],
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        assert "OK" in result or "ok" in result.lower()
        print(f"LLM connection test passed: {result}")
        
    except Exception as e:
        pytest.fail(f"Failed to connect to LLM API: {e}")


@pytest.mark.smoke
@pytest.mark.real
@pytest.mark.asyncio
async def test_mcp_agent_initialization(real_mcp_agent):
    """MCPエージェントの初期化確認"""
    assert real_mcp_agent is not None
    assert real_mcp_agent.llm_interface is not None  # LLMInterfaceを確認
    assert real_mcp_agent.config is not None
    
    # 基本的な設定が読み込まれているか確認
    assert hasattr(real_mcp_agent.config, 'llm')
    assert hasattr(real_mcp_agent.config.llm, 'model')
    
    print(f"MCP Agent initialized with model: {real_mcp_agent.config.llm.model}")


@pytest.mark.smoke
@pytest.mark.real
def test_environment_variables():
    """必要な環境変数の確認"""
    # オプション環境変数のチェック
    optional_vars = {
        "RUN_EXPENSIVE_TESTS": "false",
        "MAX_API_CALLS": "10",
        "SKIP_EXPENSIVE": "true"
    }
    
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"{var}: {value}")
    
    # 最低限必要な設定の確認
    assert os.path.exists("tests"), "Test directory not found"
    assert os.path.exists("pytest.ini"), "pytest.ini not found"