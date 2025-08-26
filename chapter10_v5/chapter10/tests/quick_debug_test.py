#!/usr/bin/env python3
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connection_manager import ConnectionManager

async def quick_test():
    os.environ["SURROGATE_POLICY"] = "replace"
    cm = ConnectionManager('mcp_servers.json', verbose=False)
    await cm.initialize()
    result = await cm.call_tool('execute_python', {'code': "print('円盤を移動')"})
    print('Result:', result)
    await cm.close()

if __name__ == "__main__":
    asyncio.run(quick_test())