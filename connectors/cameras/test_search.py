#!/usr/bin/env python3
"""
Test script for camera search functionality
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from camera_index import CameraIndex

def test_search():
    """Test various search scenarios"""
    index = CameraIndex()
    index.load()

    print(f"✓ Loaded {len(index.models)} camera models\n")
    print("=" * 80)

    test_cases = [
        ("trassir", "Search by brand only"),
        ("trassir:", "Brand with colon (empty model)"),
        ("trassir: 2141", "Brand + model with colon"),
        ("trassir 2141", "Brand + model with space"),
        ("2141", "Search by model only"),
        ("255 ip cam", "Multi-word brand"),
        ("255 ip cam: model", "Multi-word brand + model"),
        ("hikvision ds-2cd", "Partial brand + partial model"),
        ("tp-link: c200", "Brand with dash + model"),
        ("tp-link c200", "Brand with dash + model (space)"),
        ("Trassir: D2B5", "Case variation"),
        ("hikv", "Partial brand match"),
        ("d-link", "Brand with dash"),
        ("d-link:", "Brand with dash (empty model)"),
        ("   trassir   ", "Query with extra spaces"),
        ("HIKVISION", "Uppercase query"),
    ]

    for query, description in test_cases:
        print(f"\n📝 Test: {description}")
        print(f"   Query: '{query}'")
        print("-" * 80)

        results = index.search(query, limit=10)

        if results:
            print(f"   ✓ Found {len(results)} results:")
            for i, result in enumerate(results[:5], 1):  # Show first 5
                display = result.get('display', 'N/A')
                print(f"     {i}. {display}")
            if len(results) > 5:
                print(f"     ... and {len(results) - 5} more")
        else:
            print("   ✗ No results found")

        print("-" * 80)

    print("\n" + "=" * 80)
    print("✓ All tests completed!")

if __name__ == '__main__':
    test_search()
