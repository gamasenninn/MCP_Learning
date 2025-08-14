#!/usr/bin/env python3
"""
HTTP Transport MCPサーバー（IP電話対応版）
"""

from fastmcp import FastMCP

mcp = FastMCP("HTTP Calculator")

@mcp.tool()
def add(a: float, b: float) -> float:
    """二つの数値を足し算します"""
    return a + b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """二つの数値を掛け算します"""
    return a * b

@mcp.tool()
def calculate_power(base: float, exponent: float) -> float:
    """べき乗を計算します（base の exponent 乗）"""
    return base ** exponent

if __name__ == "__main__":
    print("🌐 HTTP MCP Server starting...")
    print("📡 Endpoint: http://localhost:8000/mcp")
    print("🔧 Tools: add, multiply, calculate_power")
    
    # HTTP Transportで起動
    mcp.run(
        transport="http",
        host="localhost", 
        port=8000,
        path="/mcp"
    )