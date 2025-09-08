#!/usr/bin/env python3
"""
pytest configuration and shared fixtures
MCP Agent テストの共通設定とフィクスチャ
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import Config, DisplayConfig, LLMConfig, ExecutionConfig, ConversationConfig, DevelopmentConfig

from state_manager import StateManager, TaskState
from task_manager import TaskManager
from mcp_agent import MCPAgent
from connection_manager import ConnectionManager


@pytest.fixture(scope="session")
def event_loop():
    """共通のイベントループ"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """一時ディレクトリ"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_config():
    """モック設定"""
    return Config(
        display=DisplayConfig(
            ui_mode="basic",
            show_timing=False,
            show_thinking=False
        ),
        llm=LLMConfig(
            model="gpt-4o-mini",
            temperature=0.2,
            reasoning_effort="minimal",
            max_completion_tokens=1000
        ),
        execution=ExecutionConfig(
            max_retries=3,
            timeout_seconds=30,
            max_tasks=10
        ),
        conversation=ConversationConfig(
            context_limit=10,
            max_history=50
        ),
        development=DevelopmentConfig(
            verbose=False
        )
    )


@pytest.fixture
def mock_llm_client():
    """LLMクライアントのモック"""
    client = MagicMock()
    
    # Chat completion mockの設定
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"test": "response"}'
    mock_response.usage = MagicMock()
    mock_response.usage.total_tokens = 100
    
    client.chat.completions.create = AsyncMock(return_value=mock_response)
    return client


@pytest_asyncio.fixture
async def state_manager(temp_dir):
    """StateManagerのフィクスチャ"""
    state_dir = Path(temp_dir) / ".mcp_agent"
    manager = StateManager(state_dir=str(state_dir))
    yield manager
    # cleanup handled by temp_dir fixture


@pytest.fixture
def task_manager():
    """TaskManagerのフィクスチャ"""
    # TaskManagerの実際の初期化パラメータを確認して調整
    # モックStateManagerを使用
    mock_state_manager = MagicMock()
    return TaskManager(state_manager=mock_state_manager)


@pytest.fixture
def sample_tasks():
    """サンプルタスクのリスト"""
    return [
        TaskState(
            task_id="test_001",
            tool="multiply",
            params={"a": 5, "b": 10},
            description="5に10を掛ける",
            status="pending"
        ),
        TaskState(
            task_id="test_002", 
            tool="subtract",
            params={"a": "前の計算結果", "b": 20},
            description="結果から20を引く",
            status="pending"
        )
    ]


@pytest_asyncio.fixture
async def mcp_agent_mock(temp_dir, mock_config, mock_llm_client):
    """MCPAgentのモック"""
    # 一時的に設定を保存
    config_path = Path(temp_dir) / "config.yaml"
    
    agent = MCPAgent()
    agent.config = mock_config
    agent.llm = mock_llm_client
    
    # ConnectionManagerもモック
    agent.connection_manager = MagicMock()
    agent.connection_manager.call_tool = AsyncMock(return_value="test_result")
    agent.connection_manager.format_tools_for_llm = MagicMock(return_value="tool_info")
    
    # TaskExecutorのLLMもモックに置き換え
    if hasattr(agent, 'task_executor'):
        agent.task_executor.llm = mock_llm_client
        # ErrorHandlerのLLMもモックに置き換え
        if hasattr(agent.task_executor, 'error_handler') and agent.task_executor.error_handler:
            agent.task_executor.error_handler.llm = mock_llm_client
    
    return agent


@pytest.fixture
def sample_session_data():
    """サンプルセッションデータ"""
    return {
        "session_id": "test_session_001",
        "created_at": "2025-08-30T12:00:00.000000",
        "last_active": "2025-08-30T12:30:00.000000",
        "conversation_context": [
            {
                "role": "user",
                "content": "テストメッセージ",
                "timestamp": "2025-08-30T12:00:10.000000"
            }
        ],
        "current_user_query": "テストクエリ",
        "execution_type": "TOOL",
        "pending_tasks": [],
        "completed_tasks": []
    }


# pytest設定（マーカーはpytest.iniで定義）


# テスト実行前の共通セットアップ
@pytest.fixture(autouse=True)
def setup_test_environment():
    """全テストで実行される共通セットアップ"""
    # .env.testファイルから環境変数を読み込み（存在する場合）
    from dotenv import load_dotenv
    env_test_path = Path(__file__).parent.parent / ".env.test"
    if env_test_path.exists():
        load_dotenv(env_test_path, override=False)  # 既存の環境変数を上書きしない
    
    # 環境変数の設定など（.env.testにない場合のデフォルト）
    os.environ.setdefault("OPENAI_API_KEY", "test_key")
    yield
    # cleanup


# ========== リアル環境用フィクスチャ ==========

@pytest.fixture
def real_api_key():
    """実際のAPI KEY（環境変数から取得）"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "test_key":
        pytest.skip("Real OPENAI_API_KEY required for this test")
    return api_key


@pytest_asyncio.fixture
async def real_llm_client(real_api_key):
    """実際のOpenAI APIクライアント（非推奨、後方互換性のため保持）"""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=real_api_key)
        yield client
    except ImportError:
        pytest.skip("openai package required for real tests")


@pytest_asyncio.fixture
async def real_mcp_agent(temp_dir, real_api_key):
    """実際のMCPエージェント（モックなし）"""
    os.environ["OPENAI_API_KEY"] = real_api_key
    agent = MCPAgent()
    await agent.initialize()
    yield agent
    # cleanupメソッドがある場合のみ実行
    if hasattr(agent, 'cleanup'):
        await agent.cleanup()
    elif hasattr(agent, 'connection_manager') and hasattr(agent.connection_manager, 'close_all'):
        await agent.connection_manager.close_all()


@pytest.fixture
def use_real_services(request):
    """リアルサービス使用フラグ"""
    # コマンドラインオプションまたは環境変数から取得
    return request.config.getoption("--real", default=False) or \
           os.getenv("RUN_REAL_TESTS", "false").lower() == "true"


@pytest.fixture
def max_api_calls():
    """API呼び出し回数制限"""
    return int(os.getenv("MAX_API_CALLS", "10"))


@pytest.fixture
def skip_expensive(request):
    """高額なテストをスキップするかどうか"""
    if request.node.get_closest_marker("expensive"):
        if os.getenv("RUN_EXPENSIVE_TESTS", "false").lower() != "true":
            pytest.skip("Expensive test skipped (set RUN_EXPENSIVE_TESTS=true to run)")


# pytest用のオプション追加
def pytest_addoption(parser):
    parser.addoption(
        "--real",
        action="store_true",
        default=False,
        help="Run tests with real services"
    )
    parser.addoption(
        "--skip-expensive",
        action="store_true",
        default=False,
        help="Skip expensive tests"
    )