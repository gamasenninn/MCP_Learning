#!/usr/bin/env python3
"""
エラーハンドリングテストの簡易実行版
結果をより分かりやすく表示
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from test_error_handling import ErrorHandlingTester

async def run_summary_test():
    """サマリテストを実行"""
    
    print("\n" + "=" * 70)
    print(" 第10章 インテリジェントエラーハンドリング - 動作確認")
    print("=" * 70)
    
    # APIキーの確認
    api_key = os.getenv("OPENAI_API_KEY")
    use_ai = bool(api_key)
    
    print(f"\n[環境]")
    print(f"  OpenAI API: {'利用可能' if use_ai else '利用不可（基本モードで実行）'}")
    
    # テスターを作成（簡潔モード）
    tester = ErrorHandlingTester(use_ai=use_ai)
    
    # ExecutorのverboseをFalseに設定
    import io
    from contextlib import redirect_stdout
    
    # セットアップ時の出力を抑制
    print(f"\n[準備] テスト環境をセットアップ中...")
    f = io.StringIO()
    with redirect_stdout(f):
        await tester.setup()
    
    # Executorのverboseフラグを無効化
    if tester.executor:
        tester.executor.verbose = False
    
    # 各テストを実行（簡潔なログ）
    print(f"\n[テスト実行]")
    print("-" * 60)
    
    results = []
    
    # テスト1: パラメータエラー
    print("1. パラメータエラーの自動修正...", end="", flush=True)
    result1 = await run_quiet_test(tester.test_parameter_error)
    results.append(("パラメータエラー修正", result1))
    print(f" {'[OK]' if result1['success'] else '[NG]'} ({result1['elapsed']:.1f}秒)")
    
    # テスト2: ゼロ除算エラー
    print("2. ゼロ除算エラーの回避...", end="", flush=True)
    result2 = await run_quiet_test(tester.test_zero_division)
    results.append(("ゼロ除算回避", result2))
    print(f" {'[OK]' if result2['success'] else '[NG]'} ({result2['elapsed']:.1f}秒)")
    
    # テスト3: ツール不在エラー
    print("3. 存在しないツールの代替...", end="", flush=True)
    result3 = await run_quiet_test(tester.test_tool_not_found)
    results.append(("ツール代替", result3))
    print(f" {'[OK]' if result3['success'] else '[NG]'} ({result3['elapsed']:.1f}秒)")
    
    # テスト4: 複雑な計算エラー
    print("4. 複雑な計算エラーの分解...", end="", flush=True)
    result4 = await run_quiet_test(tester.test_complex_calculation_error)
    results.append(("計算エラー分解", result4))
    print(f" {'[OK]' if result4['success'] else '[NG]'} ({result4['elapsed']:.1f}秒)")
    
    # テスト5: 接続エラー
    print("5. 接続エラーのリトライ...", end="", flush=True)
    result5 = await run_quiet_test(tester.test_connection_error_simulation)
    results.append(("接続リトライ", result5))
    print(f" {'[OK]' if result5['success'] else '[NG]'} ({result5['elapsed']:.1f}秒)")
    
    # 結果サマリ
    print("\n" + "=" * 70)
    print(" テスト結果サマリ")
    print("=" * 70)
    
    success_count = sum(1 for _, r in results if r['success'])
    total_count = len(results)
    recovered_count = sum(1 for _, r in results if r.get('recovered', False))
    
    print(f"\n[統計]")
    print(f"  成功率: {success_count}/{total_count} ({success_count/total_count*100:.0f}%)")
    print(f"  AIリカバリー: {recovered_count}件")
    print(f"  総実行時間: {sum(r['elapsed'] for _, r in results):.1f}秒")
    
    print(f"\n[個別結果]")
    for name, result in results:
        status = "✓" if result['success'] else "✗"
        recovery = " (AIリカバリー)" if result.get('recovered') else ""
        print(f"  {status} {name}: {result['elapsed']:.1f}秒{recovery}")
    
    # AI機能の統計
    if use_ai and tester.executor:
        ai_fixes = len([a for a in tester.executor.execution_history if a.fix_applied])
        if ai_fixes > 0:
            print(f"\n[AI支援]")
            print(f"  修正提案: {ai_fixes}件")
            print(f"  成功率: {(recovered_count/ai_fixes*100):.0f}%" if ai_fixes > 0 else "N/A")
    
    # クリーンアップ
    await tester.cleanup()
    
    print("\n" + "=" * 70)
    if success_count == total_count:
        print(" [SUCCESS] 全テスト成功！エラーハンドリングが正常に動作しています")
    else:
        print(f" [PARTIAL] {success_count}/{total_count}のテストが成功しました")
    print("=" * 70)

async def run_quiet_test(test_func):
    """テストを静かに実行"""
    # 実際のテスト関数をそのまま実行
    # (ErrorHandlingTesterのverboseフラグで制御)
    return await test_func()

if __name__ == "__main__":
    asyncio.run(run_summary_test())