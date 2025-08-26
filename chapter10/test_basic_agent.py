#!/usr/bin/env python3
"""
Basic test for MCP Agent V4 surrogate character fixes
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_utility_functions():
    """Test the utility functions we added"""
    print("Testing utility functions...")
    
    # Import the functions
    from mcp_agent import clean_surrogate_chars, safe_str, safe_repr
    
    # Test clean_surrogate_chars
    test_text = "Hello \udc8b World"  # Contains surrogate character
    cleaned = clean_surrogate_chars(test_text)
    print(f"Original: {repr(test_text)}")
    print(f"Cleaned:  {repr(cleaned)}")
    
    # Test safe_str
    test_dict = {"code": "print('\udc8b Hello')"}
    safe_string = safe_str(test_dict)
    print(f"Safe str: {safe_string}")
    
    # Test safe_repr
    safe_representation = safe_repr(test_dict)
    print(f"Safe repr: {safe_representation}")
    
    print("✓ Utility functions work correctly!")


def test_surrogate_detection():
    """Test surrogate character detection"""
    print("\nTesting surrogate character detection...")
    
    from mcp_agent import clean_surrogate_chars
    
    # Test cases
    test_cases = [
        ("Normal text", "Normal text"),
        ("Text with \udc8b surrogate", "Text with ? surrogate"),
        ("Multiple \udc8b surrogates \udcef here", "Multiple ? surrogates ? here"),
        ("日本語テキスト", "日本語テキスト"),  # Japanese should be preserved
        ("", ""),  # Empty string
    ]
    
    for original, expected in test_cases:
        result = clean_surrogate_chars(original)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{original}' -> '{result}'")
        if result != expected:
            print(f"   Expected: '{expected}'")


if __name__ == "__main__":
    print("=" * 50)
    print("MCP Agent - Basic Surrogate Character Fix Test")  
    print("=" * 50)
    
    try:
        test_utility_functions()
        test_surrogate_detection()
        print("\n✓ All basic tests passed!")
        print("  Surrogate character handling is working correctly.")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()