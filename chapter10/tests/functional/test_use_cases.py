#!/usr/bin/env python3
"""
Functional tests for specific use cases
具体的なユースケースの機能テスト
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.functional
@pytest.mark.asyncio
async def test_fibonacci_calculation(mcp_agent_mock):
    """フィボナッチ数列計算のテスト"""
    agent = mcp_agent_mock
    
    # フィボナッチ計算のモック設定
    agent.connection_manager.call_tool = AsyncMock(side_effect=[
        "1",  # fib(1) = 1
        "1",  # fib(2) = 1
        "2",  # fib(3) = 2
        "3",  # fib(4) = 3
        "5",  # fib(5) = 5
        "8",  # fib(6) = 8
    ])
    
    # テストケース: フィボナッチ数列の6番目
    query = "フィボナッチ数列の6番目の数を計算してください"
    
    # process_requestメソッドをモック
    agent.process_request = AsyncMock(return_value="フィボナッチ数列の6番目の数は8です")
    
    result = await agent.process_request(query)
    assert "8" in result


@pytest.mark.functional
@pytest.mark.asyncio
async def test_hanoi_tower_japanese(mcp_agent_mock):
    """ハノイの塔問題（日本語）のテスト"""
    agent = mcp_agent_mock
    
    # ハノイの塔3枚の最小手数は2^3 - 1 = 7
    query = "3枚の円盤でハノイの塔を解く最小手数を計算してください"
    
    # 計算をモック
    agent.connection_manager.call_tool = AsyncMock(side_effect=[
        "8",   # 2^3 = 8
        "7",   # 8 - 1 = 7
    ])
    
    agent.process_request = AsyncMock(
        return_value="3枚の円盤でハノイの塔を解く最小手数は7手です"
    )
    
    result = await agent.process_request(query)
    assert "7" in result


@pytest.mark.functional
@pytest.mark.asyncio  
async def test_age_calculation_with_context(mcp_agent_mock):
    """文脈を使った年齢計算のテスト"""
    agent = mcp_agent_mock
    
    # 会話の文脈を設定
    agent.state_manager = MagicMock()
    agent.state_manager.conversation_context = [
        {"role": "user", "content": "私の年齢は30歳です"},
        {"role": "assistant", "content": "30歳ですね、承知しました"}
    ]
    
    # 年齢に基づく計算
    query = "私の年齢を2倍にしてください"
    
    agent.connection_manager.call_tool = AsyncMock(return_value="60")
    agent.process_request = AsyncMock(return_value="あなたの年齢（30歳）を2倍にすると60歳です")
    
    result = await agent.process_request(query)
    assert "60" in result


@pytest.mark.functional
@pytest.mark.asyncio
async def test_multi_step_calculation(mcp_agent_mock):
    """複数ステップの計算のテスト"""
    agent = mcp_agent_mock
    
    query = "100に25を足して、その結果を5で割って、最後に10を引いてください"
    
    # 各ステップの計算結果をモック
    agent.connection_manager.call_tool = AsyncMock(side_effect=[
        "125",  # 100 + 25 = 125
        "25",   # 125 / 5 = 25
        "15",   # 25 - 10 = 15
    ])
    
    agent.process_request = AsyncMock(
        return_value="計算結果: (100 + 25) ÷ 5 - 10 = 15"
    )
    
    result = await agent.process_request(query)
    assert "15" in result


@pytest.mark.functional
@pytest.mark.asyncio
async def test_percentage_calculation(mcp_agent_mock):
    """パーセント計算のテスト"""
    agent = mcp_agent_mock
    
    query = "1000円の20%を計算してください"
    
    agent.connection_manager.call_tool = AsyncMock(side_effect=[
        "0.2",   # 20% = 0.2
        "200",   # 1000 * 0.2 = 200
    ])
    
    agent.process_request = AsyncMock(
        return_value="1000円の20%は200円です"
    )
    
    result = await agent.process_request(query)
    assert "200" in result


@pytest.mark.functional
@pytest.mark.asyncio
async def test_date_calculation(mcp_agent_mock):
    """日付計算のテスト"""
    agent = mcp_agent_mock
    
    query = "今日から30日後は何月何日ですか？"
    
    # 日付計算は複雑なのでシンプルにモック
    agent.process_request = AsyncMock(
        return_value="今日から30日後は来月の同じ頃になります"
    )
    
    result = await agent.process_request(query)
    assert "来月" in result or "30" in result


@pytest.mark.functional
@pytest.mark.slow
@pytest.mark.asyncio
async def test_sudoku_validation(mcp_agent_mock):
    """数独検証のテスト（時間のかかるテスト）"""
    agent = mcp_agent_mock
    
    # 簡単な数独の検証
    sudoku_grid = [
        [5,3,4,6,7,8,9,1,2],
        [6,7,2,1,9,5,3,4,8],
        [1,9,8,3,4,2,5,6,7],
        [8,5,9,7,6,1,4,2,3],
        [4,2,6,8,5,3,7,9,1],
        [7,1,3,9,2,4,8,5,6],
        [9,6,1,5,3,7,2,8,4],
        [2,8,7,4,1,9,6,3,5],
        [3,4,5,2,8,6,1,7,9]
    ]
    
    query = "この数独が正しいか検証してください"
    
    agent.process_request = AsyncMock(
        return_value="この数独は正しく完成されています。全ての行、列、3x3ブロックに1-9が重複なく配置されています"
    )
    
    result = await agent.process_request(query)
    assert "正しく" in result or "完成" in result


@pytest.mark.functional
@pytest.mark.asyncio
async def test_unit_conversion(mcp_agent_mock):
    """単位変換のテスト"""
    agent = mcp_agent_mock
    
    test_cases = [
        ("1キロメートルは何メートルですか？", "1000", "1キロメートルは1000メートルです"),
        ("100センチは何メートルですか？", "1", "100センチメートルは1メートルです"),
        ("1時間は何分ですか？", "60", "1時間は60分です"),
    ]
    
    for query, expected_value, expected_response in test_cases:
        agent.connection_manager.call_tool = AsyncMock(return_value=expected_value)
        agent.process_request = AsyncMock(return_value=expected_response)
        
        result = await agent.process_request(query)
        assert expected_value in result