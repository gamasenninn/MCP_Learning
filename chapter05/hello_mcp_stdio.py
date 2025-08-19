# 最もシンプルなMCPサーバー（hello_mcp_stdio.py）
from fastmcp import FastMCP

mcp = FastMCP("Hello")

@mcp.tool()
def say_hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    # これだけでSTDIO Transportが使われる
    mcp.run()