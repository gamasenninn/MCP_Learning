#!/usr/bin/env python3
"""
あなたの最初のMCPサーバー - AI対応電卓
"""

import math
from fastmcp import FastMCP

# MCPサーバーを作成
mcp = FastMCP("My Calculator")

@mcp.tool()
def add(a: float, b: float) -> float:
    """2つの数値を加算（足し算）します。
    
    整数・小数に対応。金額計算、合計値の算出、累積計算などに使用。
    例：価格の合計、スコアの加算、距離の合算など。
    """
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """2つの数値の差を計算（引き算）します。
    
    整数・小数に対応。差額計算、残高計算、変化量の算出などに使用。
    例：割引額の計算、在庫の減算、時間差の計算など。
    """
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """2つの数値の積（掛け算）を計算します。
    
    面積計算、単価×数量、累乗計算（同じ数を2回）などに使用。
    例：「100個買ったら合計いくら？」「5メートル四方の面積は？」
    """
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """2つの数値の商（割り算）を計算します。
    
    比率計算、平均値算出、単価計算などに使用。ゼロ除算は自動的にエラー処理。
    例：「1人あたりの金額は？」「成功率は？」「時速を計算」
    """
    if b == 0:
        raise ValueError("ゼロで割ることはできません")
    return a / b

@mcp.tool()
def power(a: float, b: float) -> float:
    """累乗計算（aのb乗）を実行します。
    
    指数計算、複利計算、面積・体積の計算などに使用。
    例：「2の10乗は？」「年利5%で10年後は？」「立方体の体積」
    大きすぎる結果は自動的にエラー処理。
    """
    try:
        return a ** b
    except OverflowError:
        raise ValueError("計算結果が大きすぎます")

@mcp.tool()
def square_root(a: float) -> float:
    """平方根（ルート）を計算します。
    
    距離計算、標準偏差、ピタゴラスの定理などに使用。
    負の数には対応していません（虚数は扱わない）。
    例：「100の平方根は？」「対角線の長さを求める」
    """
    if a < 0:
        raise ValueError("負の数の平方根は計算できません")
    return math.sqrt(a)

@mcp.tool()
def circle_area(radius: float) -> float:
    """円の面積を計算します（πr²）。
    
    半径から円の面積を算出。建築、デザイン、物理計算などに使用。
    例：「半径10cmの円の面積は？」「ピザのサイズを計算」
    結果は平方単位（半径がcmなら面積はcm²）。
    """
    if radius < 0:
        raise ValueError("半径は正の数である必要があります")
    return math.pi * radius * radius

if __name__ == "__main__":
    mcp.run()