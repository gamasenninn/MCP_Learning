#!/usr/bin/env python3
"""
Integration tests for GPT-5 support
GPT-5サポートの統合テスト
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from mcp_agent import MCPAgent
from config_manager import Config, LLMConfig


@pytest.mark.integration
@pytest.mark.gpt5
@pytest.mark.asyncio
async def test_gpt5_parameter_generation(mcp_agent_mock):
    """GPT-5パラメータ生成のテスト"""
    agent = mcp_agent_mock
    agent.config.llm.model = "gpt-5-mini"
    
    # GPT-5用パラメータ生成
    params = agent._get_llm_params(
        messages=[{"role": "user", "content": "test"}],
        temperature=0.1
    )
    
    # GPT-5特有のパラメータが設定されることを確認
    assert params["model"] == "gpt-5-mini"
    assert "max_completion_tokens" in params
    assert "reasoning_effort" in params
    assert params["temperature"] == 1.0  # GPT-5は1.0に強制


@pytest.mark.integration
@pytest.mark.gpt5
@pytest.mark.asyncio
async def test_gpt4_parameter_generation(mcp_agent_mock):
    """GPT-4パラメータ生成のテスト"""
    agent = mcp_agent_mock
    agent.config.llm.model = "gpt-4o-mini"
    
    # GPT-4用パラメータ生成
    params = agent._get_llm_params(
        messages=[{"role": "user", "content": "test"}],
        temperature=0.1
    )
    
    # GPT-4用パラメータが設定されることを確認
    assert params["model"] == "gpt-4o-mini"
    assert "max_completion_tokens" not in params
    assert "reasoning_effort" not in params
    assert params["temperature"] == 0.1  # GPT-4は指定値を維持


@pytest.mark.integration
@pytest.mark.gpt5
def test_gpt5_models_support():
    """GPT-5モデルサポートのテスト"""
    agent = MCPAgent()
    
    gpt5_models = ["gpt-5-mini", "gpt-5-nano", "gpt-5"]
    
    for model in gpt5_models:
        agent.config = Config(llm=LLMConfig(model=model))
        params = agent._get_llm_params(messages=[])
        
        # 全てのGPT-5モデルで適切なパラメータが生成されることを確認
        assert params["model"] == model
        assert "max_completion_tokens" in params
        assert "reasoning_effort" in params


@pytest.mark.integration 
@pytest.mark.gpt5
def test_reasoning_effort_levels():
    """推論レベル設定のテスト"""
    agent = MCPAgent()
    agent.config = Config(
        llm=LLMConfig(
            model="gpt-5-mini",
            reasoning_effort="high", 
            max_completion_tokens=2000
        )
    )
    
    params = agent._get_llm_params(messages=[])
    
    assert params["reasoning_effort"] == "high"
    assert params["max_completion_tokens"] == 2000