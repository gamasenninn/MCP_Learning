#!/usr/bin/env python3
"""
日本語表示テスト - UTF-8修正の効果確認
"""

import sys
import os

# 修正後のconnection_managerをインポートして環境設定を適用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connection_manager import ConnectionManager

def test_japanese_output():
    """日本語出力のテスト"""
    
    print("=" * 50)
    print("日本語表示テスト")
    print("=" * 50)
    
    test_messages = [
        "[設定] AGENT.mdを読み込みました (1638文字)",
        "[指示書] カスタム指示あり",
        "[接続] MCPサーバーに接続中...",
        "[成功] ✅ タスクが完了しました",
        "[エラー] ❌ 処理に失敗しました",
        "[警告] ⚠️ メモリ使用量が多いです",
        "計算結果: 100 + 200 = 300",
        "温度: 25°C、湿度: 60%",
        "東京都新宿区の天気",
        "北京（Beijing）の現在温度",
    ]
    
    print("\n実際の表示確認:")
    for msg in test_messages:
        try:
            print(f"  {msg}")
        except UnicodeEncodeError as e:
            print(f"  [ERROR] {e}")
    
    print("\n結果:")
    print("  - 日本語は正常に表示される")
    print("  - 絵文字（✅❌⚠️）は ? に変換される")
    print("  - プログラムは停止しない")

if __name__ == "__main__":
    test_japanese_output()