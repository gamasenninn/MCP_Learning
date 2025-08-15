"""
データ分析タスクのデモ
より複雑なタスクの実行例
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent

async def sales_analysis_demo():
    """売上分析のデモ"""
    
    print("\n[Sales Analysis Demo]")
    print("="*60)
    
    agent = MCPAgent(use_mock=True)
    
    task = """
    Analyze sales data for the last quarter:
    1. Query the database for Q4 2024 sales data
    2. Calculate total revenue, average order value, and growth rate
    3. Identify top 5 products by revenue
    4. Create a summary report with insights
    """
    
    print("Task: Quarterly sales analysis")
    print("\nExecuting...")
    
    result = await agent.execute(task)
    
    if result['success']:
        print(f"\n[SUCCESS] Analysis completed")
        print(f"Report:\n{result['result']}")
        print(f"\nCompleted in {result['duration']:.2f} seconds")
    else:
        print(f"\n[FAILED] {result.get('error')}")

async def competitor_analysis_demo():
    """競合分析のデモ"""
    
    print("\n[Competitor Analysis Demo]")
    print("="*60)
    
    agent = MCPAgent(use_mock=True)
    
    task = """
    Perform competitor analysis:
    1. Search for news about top 3 competitors in the AI industry
    2. Extract key announcements and product launches
    3. Analyze their market positioning
    4. Create a comparison matrix
    5. Generate strategic recommendations
    """
    
    print("Task: AI industry competitor analysis")
    print("\nExecuting...")
    
    result = await agent.execute(task)
    
    if result['success']:
        print(f"\n[SUCCESS] Analysis completed")
        print(f"Insights:\n{result['result']}")
        print(f"\nSteps executed: {result['steps_executed']}")
    else:
        print(f"\n[FAILED] {result.get('error')}")

async def data_pipeline_demo():
    """データパイプラインのデモ"""
    
    print("\n[Data Pipeline Demo]")
    print("="*60)
    
    agent = MCPAgent(use_mock=True)
    
    task = """
    Execute data processing pipeline:
    1. Fetch raw data from multiple sources
    2. Clean and normalize the data
    3. Perform statistical analysis
    4. Generate visualizations
    5. Store processed results in database
    6. Send notification when complete
    """
    
    print("Task: Multi-source data processing pipeline")
    print("\nExecuting...")
    
    start_time = datetime.now()
    result = await agent.execute(task)
    end_time = datetime.now()
    
    if result['success']:
        print(f"\n[SUCCESS] Pipeline completed")
        print(f"Processing summary:\n{result['result']}")
        print(f"\nTotal time: {(end_time - start_time).total_seconds():.2f} seconds")
        print(f"Steps completed: {result['steps_executed']}")
    else:
        print(f"\n[FAILED] Pipeline error: {result.get('error')}")

async def interactive_demo():
    """インタラクティブデモ"""
    
    print("\n[Interactive Agent Demo]")
    print("="*60)
    print("Enter your task (or 'quit' to exit)")
    print("Example: 'Calculate the fibonacci sequence up to 10 terms'")
    print("="*60)
    
    # APIキーの確認
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[WARNING] No API key found. Using mock mode.")
        agent = MCPAgent(use_mock=True)
    else:
        print("\n[INFO] Using real mode with OpenAI API")
        agent = MCPAgent(use_mock=False)
    
    while True:
        print("\n> ", end="")
        task = input().strip()
        
        if task.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if not task:
            continue
        
        print("\nProcessing...")
        result = await agent.execute(task)
        
        if result['success']:
            print(f"\n[SUCCESS] Result:")
            print(result['result'])
            print(f"\n(Completed in {result['duration']:.2f} seconds)")
        else:
            print(f"\n[ERROR] {result.get('error')}")

async def main():
    """メイン処理"""
    
    print("\n" + "="*80)
    print(" MCP Agent - Advanced Demos")
    print("="*80)
    
    demos = [
        ("1", "Sales Analysis", sales_analysis_demo),
        ("2", "Competitor Analysis", competitor_analysis_demo),
        ("3", "Data Pipeline", data_pipeline_demo),
        ("4", "Interactive Mode", interactive_demo),
        ("5", "Run All Demos", None)
    ]
    
    print("\nAvailable demos:")
    for key, name, _ in demos[:-1]:
        print(f"  {key}. {name}")
    print(f"  {demos[-1][0]}. {demos[-1][1]}")
    print("  0. Exit")
    
    print("\nSelect demo: ", end="")
    choice = input().strip()
    
    if choice == "0":
        print("Exiting...")
        return
    elif choice == "5":
        # すべてのデモを実行
        for key, name, demo_func in demos[:-1]:
            if demo_func:
                await demo_func()
                print("\n" + "-"*60)
    else:
        # 選択されたデモを実行
        for key, name, demo_func in demos:
            if key == choice and demo_func:
                await demo_func()
                break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())