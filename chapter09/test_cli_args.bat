@echo off
echo === FastMCP CLI 引数テスト ===
echo.

echo [1] ツール一覧を表示
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter03\calculator_server.py --list
uv run python mcp_cli.py --server C:\MCP_Learning\chapter03\calculator_server.py --list
echo.
pause

echo [2] 計算実行（通常の引数）
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter03\calculator_server.py --tool add --args "a=100 b=200"
uv run python mcp_cli.py --server C:\MCP_Learning\chapter03\calculator_server.py --tool add --args "a=100 b=200"
echo.
pause

echo [3] コード実行（JSON形式）
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "{\"code\": \"print('Hello from CLI!')\"}"
uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "{\"code\": \"print('Hello from CLI!')\"}"
echo.
pause

echo [4] コード実行（key=value形式）
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "code=print('Test')"
uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "code=print('Test')"
echo.
pause

echo === テスト完了 ===