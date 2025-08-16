#!/usr/bin/env python3
"""
環境変数を.envファイルから読み込むヘルパー
"""

import os
from pathlib import Path

def load_env():
    """現在のディレクトリの.envファイルから環境変数を読み込む"""
    env_file = Path(__file__).parent / ".env"
    
    if not env_file.exists():
        print(f"[警告] .envファイルが見つかりません: {env_file}")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # コメントや空行をスキップ
            if not line or line.startswith('#'):
                continue
            
            # export文を処理
            if line.startswith('export '):
                line = line[7:]
            
            # KEY=VALUE形式を解析
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # クォートを削除
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # 環境変数に設定
                os.environ[key] = value
                print(f"[環境変数] {key}を設定しました")
    
    return True

# このモジュールがインポートされたら自動的に.envを読み込む
load_env()