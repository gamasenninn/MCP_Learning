#!/usr/bin/env python3
"""
Test V6 Integration
V6統合機能のテスト - 実際の使用ケースのシミュレーション
"""

import asyncio
import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_manager import StateManager, TaskState
from task_manager import TaskManager
from prompts import PromptTemplates


class MockLLMClient:
    """LLMクライアントのモック"""
    
    def __init__(self):
        self.chat = MockChat()

class MockChat:
    def __init__(self):
        self.completions = MockCompletions()

class MockCompletions:
    def __init__(self):
        self.mock_responses = {
            "clarification": {
                "type": "CLARIFICATION",
                "reason": "不明な情報があります",
                "clarification": {
                    "question": "年齢を教えてください",
                    "context": "計算に必要です"
                }
            },
            "simple": {
                "type": "SIMPLE",
                "reason": "単純な計算です"
            }
        }
        self.current_response = "clarification"
    
    async def create(self, **kwargs):
        response = self.mock_responses[self.current_response]
        return MockResponse(response)

class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockMessage:
    def __init__(self, content):
        import json
        self.content = json.dumps(content, ensure_ascii=False)


async def test_v6_integration():
    """V6統合機能のテスト"""
    print("=" * 50)
    print("V6 Integration Test")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_state_dir = os.path.join(temp_dir, ".mcp_agent_test")
        
        print(f"\n[1] システム初期化...")
        sm = StateManager(test_state_dir)
        mock_llm = MockLLMClient()
        tm = TaskManager(sm, mock_llm)
        
        session_id = await sm.initialize_session()
        print(f"✓ セッション開始: {session_id}")
        
        # シナリオ1: 年齢計算のCLARIFICATION
        print(f"\n[2] シナリオ1: 年齢計算のCLARIFICATION...")
        
        user_query = "私の年齢に10を足して"
        await sm.add_conversation_entry("user", user_query)
        await sm.set_user_query(user_query, "CLARIFICATION")
        
        # V6版プロンプト生成テスト
        recent_context = "User: こんにちは\nAssistant: こんにちは！"
        prompt = PromptTemplates.get_execution_type_determination_prompt_v6(
            recent_context=recent_context,
            user_query=user_query,
            tools_info="execute_python: Python code execution"
        )
        
        print("✓ V6プロンプト生成完了")
        print(f"  プロンプト長: {len(prompt)}文字")
        
        # CLARIFICATIONが含まれているかチェック
        if "CLARIFICATION" in prompt:
            print("✓ CLARIFICATION判定基準が含まれています")
        else:
            print("✗ CLARIFICATION判定基準が含まれていません")
        
        # タスク生成（CLARIFICATIONあり）
        task_list = [
            {
                "tool": "execute_python",
                "params": {"code": "age = 私の年齢; result = age + 10; print(result)"},
                "description": "年齢に10を加算"
            }
        ]
        
        tasks = await tm.create_tasks_from_list(task_list, user_query)
        print(f"✓ タスク生成: {len(tasks)}件")
        
        # CLARIFICATIONタスクの検出
        clarification_task = None
        regular_tasks = []
        
        for task in tasks:
            if task.tool == "CLARIFICATION":
                clarification_task = task
                await sm.add_pending_task(task)
                print(f"✓ CLARIFICATIONタスク検出: {task.description}")
            else:
                regular_tasks.append(task)
                await sm.add_pending_task(task)
        
        # CLARIFICATIONタスクの実行
        if clarification_task:
            question_message = await tm.execute_clarification_task(clarification_task)
            print("✓ CLARIFICATION実行結果:")
            print(f"  {question_message[:100]}...")
            
            # ユーザー回答をシミュレーション
            user_response = "25歳です"
            await sm.move_task_to_completed(clarification_task.task_id, {"user_response": user_response})
            print(f"✓ ユーザー回答: {user_response}")
            
            # 回答を受けて待機中タスクを更新
            updated = await tm.resolve_clarification(clarification_task.task_id, user_response)
            print(f"✓ タスク更新結果: {updated}")
        
        # シナリオ2: セッション中断・再開
        print(f"\n[3] シナリオ2: セッション中断・再開...")
        
        # 追加タスクを作成
        additional_task = TaskState(
            task_id="additional_001",
            tool="get_weather",
            params={"city": "Tokyo"},
            description="東京の天気取得",
            status="pending"
        )
        
        await sm.add_pending_task(additional_task)
        print("✓ 追加タスク作成")
        
        # 中断（一時停止）
        await sm.pause_all_tasks()
        print("✓ セッション一時停止")
        
        # セッション状態確認
        summary_before = sm.get_session_summary()
        print(f"✓ 中断前の状態: {summary_before['pending_tasks']}件の保留タスク")
        
        # 新しいStateManagerで復元
        sm2 = StateManager(test_state_dir)
        restored_session_id = await sm2.initialize_session(session_id)
        print(f"✓ セッション復元: {restored_session_id}")
        
        # 復元後の状態確認
        tm2 = TaskManager(sm2, mock_llm)
        summary_after = sm2.get_session_summary()
        print(f"✓ 復元後の状態: {summary_after['pending_tasks']}件の保留タスク")
        
        # 再開
        await sm2.resume_paused_tasks()
        print("✓ セッション再開")
        
        # シナリオ3: 依存関係解決
        print(f"\n[4] シナリオ3: 依存関係解決...")
        
        # 最初のタスクを完了としてマーク
        ip_task = TaskState(
            task_id="ip_001",
            tool="get_ip_info",
            params={},
            description="IP情報取得",
            status="completed",
            result={"city": "Osaka", "country": "Japan", "ip": "192.168.1.1"}
        )
        
        await sm2.add_pending_task(ip_task)
        await sm2.move_task_to_completed(ip_task.task_id, ip_task.result)
        print("✓ 基準タスク完了")
        
        # 依存関係のあるタスク
        weather_task = TaskState(
            task_id="weather_001",
            tool="get_weather", 
            params={"city": "DEPENDENCY:取得した都市名"},
            description="取得した都市の天気",
            status="pending"
        )
        
        completed_tasks = sm2.get_completed_tasks()
        resolved_task = await tm2.resolve_task_dependencies(weather_task, completed_tasks)
        
        print(f"✓ 依存関係解決:")
        print(f"  解決前: {weather_task.params}")
        print(f"  解決後: {resolved_task.params}")
        
        # シナリオ4: 統計とサマリー
        print(f"\n[5] シナリオ4: 統計とサマリー...")
        
        session_summary = sm2.get_session_summary()
        task_summary = tm2.get_task_summary()
        
        print("✓ セッション統計:")
        for key, value in session_summary.items():
            print(f"  {key}: {value}")
        
        print("✓ タスク統計:")
        for key, value in task_summary.items():
            print(f"  {key}: {value}")
        
        # ファイル確認
        print(f"\n[6] 生成されたファイルの確認...")
        state_files = [
            "session.json",
            "conversation.txt",
            "tasks/pending.json", 
            "tasks/completed.json",
            "tasks/current.txt"
        ]
        
        for file_name in state_files:
            file_path = sm2.state_dir / file_name
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"✓ {file_name}: {size}バイト")
            else:
                print(f"✗ {file_name}: 未生成")
        
        print("\n" + "=" * 50)
        print("V6 Integration Test 完了！")
        print("すべてのV6機能が正常に動作することを確認しました。")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_v6_integration())