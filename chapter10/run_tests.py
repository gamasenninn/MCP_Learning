#!/usr/bin/env python3
"""
Test runner script for MCP Agent
pytest実行用のスクリプト - リファクタリング時の検証を高速化
"""

import subprocess
import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# .env.testファイルから環境変数を読み込み
env_test_path = Path(__file__).parent / ".env.test"
if env_test_path.exists():
    load_dotenv(env_test_path)
    print(f".env.testから環境変数を読み込みました: {env_test_path}")


def run_command(cmd, description):
    """コマンド実行"""
    print(f"\n{description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode == 0:
        print(f"{description} - 成功")
    else:
        print(f"{description} - 失敗 (exit code: {result.returncode})")
        
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="MCP Agent テスト実行")
    parser.add_argument("--type", choices=["unit", "integration", "functional", "all"], 
                       default="all", help="実行するテストタイプ")
    parser.add_argument("--coverage", action="store_true", 
                       help="カバレッジレポート生成")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="詳細出力")
    parser.add_argument("--fast", action="store_true", 
                       help="高速実行（slowテストをスキップ）")
    parser.add_argument("--parallel", "-j", type=int, 
                       help="並列実行数")
    
    args = parser.parse_args()
    
    # 基本コマンド（uvを使って仮想環境で実行）
    cmd = ["uv", "run", "python", "-m", "pytest"]
    
    # テストタイプ指定
    if args.type == "unit":
        cmd.append("tests/unit")
    elif args.type == "integration": 
        cmd.append("tests/integration")
    elif args.type == "functional":
        cmd.append("tests/functional")
    else:
        cmd.append("tests")
    
    # オプション追加
    if args.coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
        
    if args.verbose:
        cmd.append("-vv")
    else:
        # verbose指定がない場合でも、テスト関数名は表示する
        cmd.append("-v")
        
    if args.fast:
        cmd.extend(["-m", "not slow"])
        
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])
    
    # 常に警告を無効化
    cmd.append("--disable-warnings")
    
    # 実行
    print("MCP Agent テスト実行")
    print(f"テストタイプ: {args.type}")
    
    success = run_command(cmd, f"{args.type.title()} テスト実行")
    
    if success:
        print(f"\n全ての{args.type}テストが成功しました！")
    else:
        print(f"\n{args.type}テストで失敗がありました")
        sys.exit(1)
    
    # カバレッジレポート表示
    if args.coverage and success:
        print("\nカバレッジレポートが htmlcov/index.html に生成されました")


def quick_test():
    """クイックテスト - リファクタリング後の基本チェック"""
    print("クイックテスト実行")
    
    # 単体テストのみ高速実行
    cmd = [
        "uv", "run", "python", "-m", "pytest", 
        "tests/unit",
        "-x",  # 最初の失敗で停止
        "--tb=short",  # 短いトレースバック
        "-v",   # テスト関数名を表示
        "--disable-warnings"  # 警告を無効化
    ]
    
    success = run_command(cmd, "クイック単体テスト")
    
    if success:
        print("基本機能OK - 開発を続行できます")
    else:
        print("基本機能に問題あり - 修正が必要です") 
        sys.exit(1)


def smoke_test():
    """スモークテスト - 最重要機能のみチェック"""
    print("スモークテスト実行")
    
    cmd = [
        "uv", "run", "python", "-m", "pytest",
        "-k", "test_state_manager_initialization or test_gpt5_parameter_generation",
        "-x", "--tb=short", "-q", "--disable-warnings"
    ]
    
    success = run_command(cmd, "スモークテスト")
    
    if success:
        print("コア機能OK")
    else:
        print("コア機能に問題あり")
        sys.exit(1)


def real_test():
    """リアルテスト - 実際のAPI/サービスを使用"""
    print("リアルテスト実行 (API KEY必要)")
    
    # API KEYチェック
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "test_key":
        print("警告: OPENAI_API_KEYが設定されていません")
        print("以下のいずれかの方法で設定してください:")
        print("1. .env.testファイルに記載 (推奨)")
        print("   cp .env.test.example .env.test")
        print("   その後、.env.testでOPENAI_API_KEY=sk-xxxを設定")
        print("2. 環境変数として設定")
        print("   export OPENAI_API_KEY=your-api-key-here")
        return False
    else:
        # API KEYの一部をマスク表示
        masked_key = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 11 else "***"
        print(f"API KEY検出: {masked_key}")
    
    cmd = [
        "uv", "run", "python", "-m", "pytest",
        "tests",
        "-m", "real",
        "--real",  # カスタムオプション
        "-v",
        "--disable-warnings"
    ]
    
    if os.getenv("SKIP_EXPENSIVE", "true").lower() == "true":
        cmd.extend(["-m", "real and not expensive"])
        print("高額テストをスキップします (SKIP_EXPENSIVE=false で実行)")
    
    return run_command(cmd, "リアルテスト")


def e2e_test():
    """E2Eテスト - エンドツーエンドの実環境テスト"""
    print("E2Eテスト実行")
    
    cmd = [
        "uv", "run", "python", "-m", "pytest",
        "tests/e2e",
        "--real",
        "-v",
        "--disable-warnings"
    ]
    
    return run_command(cmd, "E2Eテスト")


if __name__ == "__main__":
    # コマンドライン引数に応じて実行モード変更
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            quick_test()
        elif sys.argv[1] == "smoke":
            smoke_test()
        elif sys.argv[1] == "real":
            real_test()
        elif sys.argv[1] == "e2e":
            e2e_test()
        else:
            main()
    else:
        main()