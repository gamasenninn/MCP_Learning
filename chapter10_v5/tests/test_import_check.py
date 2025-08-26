#!/usr/bin/env python3
"""
Simple import test to verify path fixing works
"""
import sys
import os

# Add parent directory (chapter10) to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("Testing import path...")
    from mcp_agent import MCPAgent
    print("✓ MCPAgent import successful!")
    
    from utils import safe_str
    print("✓ utils import successful!")
    
    from prompts import PromptTemplates
    print("✓ prompts import successful!")
    
    print("\nAll imports work correctly! Tests can be run from tests/ directory.")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
    print("Path fixing needs adjustment.")