@echo off
echo === Windows環境でのコマンドライン引数テスト ===
echo.

echo [1] シンプルなコード（引用符なし）
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "code=print(123)"
uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "code=print(123)"
echo.
pause

echo [2] JSON形式（推奨）
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "{\"code\": \"print('Hello from CLI!')\"}"
uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "{\"code\": \"print('Hello from CLI!')\"}"
echo.
pause

echo [3] 複数行のコード（JSON形式）
echo コマンド: uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "{\"code\": \"for i in range(3):\n    print(f'Count: {i}')\"}"
uv run python mcp_cli.py --server C:\MCP_Learning\chapter08\universal_tools_server.py --tool execute_python --args "{\"code\": \"for i in range(3):\n    print(f'Count: {i}')\"}"
echo.
pause

echo === テスト完了 ===