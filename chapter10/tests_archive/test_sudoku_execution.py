#!/usr/bin/env python3
"""
Test script for debugging surrogate character issue in sudoku execution
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connection_manager import ConnectionManager

# Sudoku code that's causing the issue
SUDOKU_CODE = """def solve_sudoku(board):
    def is_valid(num, pos):
        # Check row
        for i in range(9):
            if board[pos[0]][i] == num and pos[1] != i:
                return False
        
        # Check column
        for i in range(9):
            if board[i][pos[1]] == num and pos[0] != i:
                return False
        
        # Check 3x3 box
        box_x = pos[1] // 3
        box_y = pos[0] // 3
        
        for i in range(box_y * 3, box_y * 3 + 3):
            for j in range(box_x * 3, box_x * 3 + 3):
                if board[i][j] == num and (i, j) != pos:
                    return False
        
        return True
    
    def find_empty():
        for i in range(9):
            for j in range(9):
                if board[i][j] == 0:
                    return (i, j)
        return None
    
    empty = find_empty()
    if not empty:
        return True
    else:
        row, col = empty
    
    for i in range(1, 10):
        if is_valid(i, (row, col)):
            board[row][col] = i
            
            if solve_sudoku(board):
                return True
            
            board[row][col] = 0
    
    return False

# Example sudoku puzzle
board = [
    [5,3,0,0,7,0,0,0,0],
    [6,0,0,1,9,5,0,0,0],
    [0,9,8,0,0,0,0,6,0],
    [8,0,0,0,6,0,0,0,3],
    [4,0,0,8,0,3,0,0,1],
    [7,0,0,0,2,0,0,0,6],
    [0,6,0,0,0,0,2,8,0],
    [0,0,0,4,1,9,0,0,5],
    [0,0,0,0,8,0,0,7,9]
]

print("Original puzzle:")
for row in board:
    print(row)

if solve_sudoku(board):
    print("\\nSolved puzzle:")
    for row in board:
        print(row)
else:
    print("No solution exists")
"""

async def test_sudoku_execution():
    """Test sudoku code execution with debugging"""
    print("=" * 50)
    print("Testing Sudoku Execution with Surrogate Character Debugging")
    print("=" * 50)
    
    # Check for surrogate characters in the original code
    print("\n[1] Checking original code for surrogate characters...")
    surrogate_count = 0
    for i, char in enumerate(SUDOKU_CODE):
        if 0xDC00 <= ord(char) <= 0xDFFF or 0xD800 <= ord(char) <= 0xDBFF:
            surrogate_count += 1
            print(f"  Found surrogate at position {i}: {repr(char)} (U+{ord(char):04X})")
    
    if surrogate_count == 0:
        print("  No surrogate characters found in original code")
    else:
        print(f"  Total surrogate characters found: {surrogate_count}")
    
    # Initialize connection manager with verbose mode
    print("\n[2] Initializing connection manager...")
    cm = ConnectionManager(verbose=True)
    
    try:
        await cm.initialize()
        
        # Check if execute_python tool is available
        tools = cm.get_available_tools()
        print(f"\n[3] Available tools: {tools}")
        
        if "execute_python" not in tools:
            print("ERROR: execute_python tool not available!")
            return
        
        # Get tool info
        tool_info = cm.get_tool_info("execute_python")
        print(f"\n[4] execute_python tool info:")
        print(f"  Server: {tool_info.get('server')}")
        print(f"  Description: {tool_info.get('description')}")
        
        # Execute the sudoku code
        print("\n[5] Executing sudoku code...")
        print("  Code length:", len(SUDOKU_CODE))
        
        # Add extra debugging
        print("\n[6] DEBUG: About to call execute_python...")
        result = await cm.call_tool("execute_python", {"code": SUDOKU_CODE})
        
        print("\n[7] Execution result:")
        print(result)
        
    except Exception as e:
        print(f"\n[ERROR] Execution failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Extra debugging for encoding errors
        if "surrogates not allowed" in str(e):
            print("\n[DEBUG] Surrogate character error detected!")
            print("  This means surrogate characters are still present when encoding")
            
    finally:
        await cm.close()
        print("\n[8] Connection manager closed")

if __name__ == "__main__":
    asyncio.run(test_sudoku_execution())