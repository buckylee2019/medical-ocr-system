#!/usr/bin/env python3
"""
Debug script to test the enhanced voting system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import run_enhanced_voting_system, CLAUDE_SONNET_MODEL_ID, CLAUDE_HAIKU_MODEL_ID, CLAUDE_SONNET_LATEST_MODEL_ID
import json

def test_model_ids():
    """Test if model IDs are correctly configured"""
    print("🔍 Testing Model IDs Configuration:")
    print(f"Claude 3.5 Sonnet: {CLAUDE_SONNET_MODEL_ID}")
    print(f"Claude 3 Haiku: {CLAUDE_HAIKU_MODEL_ID}")
    print(f"Claude 3.7 Sonnet: {CLAUDE_SONNET_LATEST_MODEL_ID}")
    print()

def test_with_sample_image():
    """Test with a sample image (you need to provide the path)"""
    # You would need to provide an actual image file path here
    sample_image_path = "/path/to/your/test/image.png"
    
    if not os.path.exists(sample_image_path):
        print("❌ Sample image not found. Please provide a valid image path.")
        return
    
    try:
        with open(sample_image_path, 'rb') as f:
            image_data = f.read()
        
        print("🧪 Testing Enhanced Voting System...")
        result = run_enhanced_voting_system(image_data)
        
        print("📊 Result Structure:")
        print(json.dumps({
            "has_individual_results": "individual_results" in result,
            "has_voting_result": "voting_result" in result,
            "has_summary": "summary" in result,
        }, indent=2))
        
        if "voting_result" in result:
            voting_result = result["voting_result"]
            print("🗳️ Voting Result Structure:")
            print(json.dumps({
                "has_final_result": "final_result" in voting_result,
                "has_vote_details": "vote_details" in voting_result,
                "has_successful_models": "successful_models" in voting_result,
                "has_total_models": "total_models" in voting_result,
            }, indent=2))
            
            if "final_result" in voting_result:
                print("✅ final_result exists!")
                print("📋 Final Result Keys:", list(voting_result["final_result"].keys()))
            else:
                print("❌ final_result missing!")
                print("Available keys:", list(voting_result.keys()))
        else:
            print("❌ voting_result missing!")
            print("Available keys:", list(result.keys()))
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

def test_empty_results():
    """Test how the system handles empty or failed results"""
    print("🧪 Testing Empty Results Handling...")
    
    # Simulate empty results
    empty_results = []
    
    from app import analyze_and_vote
    result = analyze_and_vote(empty_results)
    
    print("📊 Empty Results Structure:")
    print(json.dumps(result, indent=2))
    
    # Test with failed results
    failed_results = [
        {"success": False, "model": "test-model", "run_number": 1, "error": "Test error"}
    ]
    
    result = analyze_and_vote(failed_results)
    print("📊 Failed Results Structure:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    print("🚀 Medical OCR Debug Test")
    print("=" * 50)
    
    test_model_ids()
    test_empty_results()
    
    print("\n💡 To test with actual image:")
    print("1. Update sample_image_path in test_with_sample_image()")
    print("2. Uncomment the test_with_sample_image() call")
    print("3. Make sure your AWS credentials are configured")
    
    # Uncomment this line when you have a test image
    # test_with_sample_image()
