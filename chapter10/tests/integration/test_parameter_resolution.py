#!/usr/bin/env python3
"""
Integration tests for parameter resolution
パラメータ解決機能の統合テスト
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
import json

from mcp_agent import MCPAgent
from state_manager import TaskState


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parameter_resolution_with_context(mcp_agent_mock):
    """実行文脈を使ったパラメータ解決のテスト"""
    agent = mcp_agent_mock
    
    # モックLLMレスポンス設定
    agent.llm.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "resolved_params": {"a": 325, "b": 200},
        "reasoning": "前の計算結果325を使用"
    })
    
    # 実行文脈
    execution_context = [
        {
            "success": True,
            "result": "65 × 5 = 325",
            "task_description": "年齢に5を掛ける"
        }
    ]
    
    # パラメータ解決対象のタスク
    task = TaskState(
        task_id="test_002",
        tool="subtract", 
        params={"a": "前の計算結果", "b": 200},
        description="結果から200を引く",
        status="pending"
    )
    
    # パラメータ解決実行
    resolved_params = await agent.task_executor.resolve_parameters_with_llm(task, execution_context)
    
    # 「前の計算結果」が325に解決されることを確認
    assert resolved_params["a"] == 325
    assert resolved_params["b"] == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parameter_resolution_without_context(mcp_agent_mock):
    """実行文脈なしのパラメータ解決のテスト"""
    agent = mcp_agent_mock
    
    # モックLLMレスポンス設定（元のパラメータをそのまま返す）
    original_params = {"a": 10, "b": 20}
    agent.llm.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "resolved_params": original_params,
        "reasoning": "実行履歴がないため元のパラメータを使用"
    })
    
    task = TaskState(
        task_id="test_001",
        tool="multiply",
        params=original_params,
        description="10に20を掛ける",
        status="pending"
    )
    
    resolved_params = await agent.task_executor.resolve_parameters_with_llm(task, [])
    
    # 元のパラメータがそのまま返されることを確認
    assert resolved_params == original_params


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parameter_resolution_json_parsing_fallback(mcp_agent_mock):
    """JSON解析フォールバック機能のテスト"""
    agent = mcp_agent_mock
    
    # LLMInterfaceのメソッドを直接モック
    expected_params = {"a": 50, "b": 75}
    agent.llm_interface.resolve_task_parameters = AsyncMock(return_value=expected_params)
    
    task = TaskState(
        task_id="test_003",
        tool="add",
        params={"a": "前の値", "b": 75},
        description="前の値に75を足す",
        status="pending"
    )
    
    resolved_params = await agent.task_executor.resolve_parameters_with_llm(task, [])
    
    # LLMInterfaceを通じたパラメータ解決が動作することを確認
    assert resolved_params["a"] == 50
    assert resolved_params["b"] == 75


@pytest.mark.integration 
@pytest.mark.asyncio
async def test_parameter_resolution_error_handling(mcp_agent_mock):
    """パラメータ解決エラー処理のテスト"""
    agent = mcp_agent_mock
    
    # 不正なJSONレスポンス
    agent.llm.chat.completions.create.return_value.choices[0].message.content = "invalid json response"
    
    original_params = {"a": "テスト", "b": 100}
    task = TaskState(
        task_id="test_error",
        tool="test_tool",
        params=original_params,
        description="エラーテスト",
        status="pending"
    )
    
    resolved_params = await agent.task_executor.resolve_parameters_with_llm(task, [])
    
    # エラー時は元のパラメータが返されることを確認
    assert resolved_params == original_params


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_context_resolution(mcp_agent_mock):
    """複数の実行文脈を使ったパラメータ解決のテスト"""
    agent = mcp_agent_mock
    
    # 複数の実行結果
    execution_context = [
        {
            "success": True,
            "result": "10 + 5 = 15", 
            "task_description": "10に5を足す"
        },
        {
            "success": True,
            "result": "15 × 2 = 30",
            "task_description": "結果に2を掛ける"
        }
    ]
    
    agent.llm.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "resolved_params": {"a": 30, "b": 10},
        "reasoning": "最新の計算結果30を使用"
    })
    
    task = TaskState(
        task_id="test_multi",
        tool="subtract",
        params={"a": "前の計算結果", "b": 10},
        description="最新結果から10を引く",
        status="pending"
    )
    
    resolved_params = await agent.task_executor.resolve_parameters_with_llm(task, execution_context)
    
    # 最新の結果が使用されることを確認
    assert resolved_params["a"] == 30
    assert resolved_params["b"] == 10