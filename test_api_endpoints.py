#!/usr/bin/env python3
"""
Quick test script for API endpoints
"""

import requests
import json

def test_api_endpoints():
    """Test the API endpoints"""
    base_url = "http://localhost:5006"
    
    print("🧪 Testing API Endpoints")
    print("=" * 50)
    
    # Test images list API
    try:
        print("📋 Testing /api/images...")
        response = requests.get(f"{base_url}/api/images", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Images API works - Found {data.get('count', 0)} images")
            
            # Find a pending review image to test
            pending_images = [img for img in data.get('images', []) if img.get('processing_status') == 'pending_review']
            if pending_images:
                test_image = pending_images[0]
                print(f"🔍 Found pending review image: {test_image['filename']}")
                
                # Test review API
                print(f"📝 Testing /api/images/{test_image['id']}/review...")
                review_response = requests.get(f"{base_url}/api/images/{test_image['id']}/review", timeout=30)
                if review_response.status_code == 200:
                    review_data = review_response.json()
                    if review_data.get('success'):
                        print("✅ Review API works")
                    else:
                        print(f"❌ Review API error: {review_data.get('error')}")
                else:
                    print(f"❌ Review API failed: {review_response.status_code}")
            else:
                print("ℹ️ No pending review images found")
        else:
            print(f"❌ Images API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ API test error: {str(e)}")

if __name__ == "__main__":
    print("🚀 API Endpoints Test")
    print("Make sure the application is running on localhost:5006")
    print()
    
    try:
        test_api_endpoints()
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
    
    print("\n💡 If tests fail:")
    print("1. Make sure 'python app.py' is running")
    print("2. Check if there are any pending review images")
    print("3. Check the console logs for detailed error messages")
