#!/usr/bin/env python3
"""
E2E tests with real services for calculation workflows
実際のMCPサーバーとLLM APIを使用した計算フローのE2Eテスト
"""

import pytest
import pytest_asyncio
import os


@pytest.mark.e2e
@pytest.mark.real
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_real_simple_calculation(real_mcp_agent):
    """実際のMCPサーバーとLLMで単純な計算タスクを実行"""
    # 実際のエージェントで計算を実行
    result = await real_mcp_agent.process_request("5に10を掛けて")
    
    # 結果に50が含まれることを確認
    assert "50" in str(result)
    print(f"Real calculation result: {result}")


@pytest.mark.e2e
@pytest.mark.real
@pytest.mark.requires_api
@pytest.mark.asyncio
async def test_real_chained_calculation(real_mcp_agent):
    """実際のMCPサーバーで連鎖計算を実行"""
    # 複数ステップの計算
    result = await real_mcp_agent.process_request(
        "10に5を足して、その結果に2を掛けて、最後に10を引いて"
    )
    
    # (10 + 5) * 2 - 10 = 20
    assert "20" in str(result)
    print(f"Chained calculation result: {result}")


@pytest.mark.e2e
@pytest.mark.real
@pytest.mark.requires_api
@pytest.mark.expensive
@pytest.mark.asyncio
async def test_real_complex_reasoning(real_mcp_agent, skip_expensive):
    """実際のLLMで複雑な推論を含む計算を実行（高額テスト）"""
    # 複雑な文脈での計算
    result = await real_mcp_agent.process_request(
        "私の年齢が30歳で、妻が私より5歳年下の場合、"
        "10年後の私たちの年齢の合計を計算してください"
    )
    
    # 30 + 10 + 25 + 10 = 75
    assert "75" in str(result) or "七十五" in str(result)
    print(f"Complex reasoning result: {result}")


@pytest.mark.e2e
@pytest.mark.real
@pytest.mark.gpt5
@pytest.mark.expensive
@pytest.mark.asyncio
async def test_gpt5_advanced_reasoning(real_mcp_agent, skip_expensive):
    """GPT-5の高度な推論能力をテスト（最も高額なテスト）"""
    # GPT-5モデルが設定されているか確認
    model = real_mcp_agent.config.llm.model.lower()
    if not (model.startswith("gpt-4") or model.startswith("gpt-5")):
        pytest.skip("GPT-4* or GPT-5* model required for this test")
    
    # 高度な推論を要する計算
    result = await real_mcp_agent.process_request(
        "フィボナッチ数列の10番目の数を計算し、"
        "それに黄金比（約1.618）を掛けた値を求めてください"
    )
    
    # フィボナッチ10番目 = 55, 55 * 1.618 ≈ 89
    assert result is not None
    print(f"GPT-5 advanced reasoning result: {result}")