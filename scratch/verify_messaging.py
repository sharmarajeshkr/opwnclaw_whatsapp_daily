import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.agents.utils import to_whatsapp_style, parse_llm_json

def test_formatting():
    print("--- Testing WhatsApp Formatting ---")
    test_cases = [
        ("# Main Header", "*MAIN HEADER*"),
        ("## Sub Header", "*SUB HEADER*"),
        ("**Bold Text**", "*Bold Text*"),
        ("[Google](https://google.com)", "Google: https://google.com"),
        ("🔹 List item", "🔹 List item"),
        ("Line 1\n\n\nLine 2", "Line 1\n\nLine 2"),
    ]
    
    for input_text, expected in test_cases:
        result = to_whatsapp_style(input_text)
        print(f"Input: {input_text!r}")
        print(f"Result: {result!r}")
        # Note: headers add newlines, so we check inclusion
        if expected in result:
            print("✅ Pass")
        else:
            print("❌ Fail")
        print("-" * 20)

def test_json_parsing():
    print("\n--- Testing LLM JSON Parsing ---")
    test_cases = [
        ('{"text": "Hello"}', {"text": "Hello"}),
        ('```json\n{"text": "Hello Block"}\n```', {"text": "Hello Block"}),
        ('Sure, here is the JSON:\n{"text": "Wrapped"}', {"text": "Wrapped"}),
        ('Some noise before\n```json\n{"text": "Noisy"}\n```\nNoise after', {"text": "Noisy"}),
    ]
    
    for input_text, expected in test_cases:
        result = parse_llm_json(input_text)
        print(f"Input: {input_text!r}")
        print(f"Result: {result!r}")
        if result == expected:
            print("✅ Pass")
        else:
            print("❌ Fail")
        print("-" * 20)

if __name__ == "__main__":
    test_formatting()
    test_json_parsing()
