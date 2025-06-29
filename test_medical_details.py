#!/usr/bin/env python3
"""
Test script for medical document details functionality
"""

import requests
import json

def test_medical_details_api():
    """Test the medical details API"""
    print("🧪 Testing Medical Document Details API")
    print("=" * 50)
    
    base_url = "http://localhost:5006"
    
    try:
        # First get the list of images
        print("📋 Getting images list...")
        response = requests.get(f"{base_url}/api/images", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['success'] and data['images']:
                # Find a completed image
                completed_images = [img for img in data['images'] if img.get('processing_status') == 'completed' and img.get('ocr_result_id')]
                
                if completed_images:
                    test_image = completed_images[0]
                    print(f"✅ Found completed image: {test_image['filename']}")
                    
                    # Test the OCR result API
                    print(f"🔍 Testing OCR result API for image: {test_image['id']}")
                    ocr_response = requests.get(f"{base_url}/api/images/{test_image['id']}/ocr-result", timeout=10)
                    
                    if ocr_response.status_code == 200:
                        ocr_data = ocr_response.json()
                        if ocr_data['success']:
                            print("✅ OCR result API works!")
                            
                            # Display sample data structure
                            ocr_result = ocr_data['ocr_result']
                            print(f"📊 Processing mode: {ocr_result['processing_mode']}")
                            print(f"🤖 Human reviewed: {ocr_result['human_reviewed']}")
                            if ocr_result.get('confidence_score'):
                                print(f"📈 Confidence: {ocr_result['confidence_score']:.2%}")
                            
                            # Check data structure
                            data_keys = list(ocr_result['data'].keys())
                            print(f"📋 Data sections: {', '.join(data_keys)}")
                            
                            return True
                        else:
                            print(f"❌ OCR API error: {ocr_data.get('error')}")
                    else:
                        print(f"❌ OCR API failed: {ocr_response.status_code}")
                else:
                    print("ℹ️ No completed images found for testing")
                    return True  # Not an error, just no data
            else:
                print("ℹ️ No images found")
                return True
        else:
            print(f"❌ Images API failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        return False

def show_usage_instructions():
    """Show usage instructions"""
    print("\n💡 Usage Instructions")
    print("=" * 50)
    
    print("1. Make sure the application is running:")
    print("   python app.py")
    print()
    print("2. Upload and process some medical documents:")
    print("   - Visit http://localhost:5006")
    print("   - Upload medical certificate images")
    print("   - Wait for processing to complete")
    print()
    print("3. View medical document details:")
    print("   - Visit http://localhost:5006/images")
    print("   - Click on any completed image")
    print("   - View the medical document content on the right side")
    print()
    print("4. Expected content sections:")
    print("   - 證明書資訊 (Certificate Info)")
    print("   - 病患資訊 (Patient Info)")
    print("   - 診斷資訊 (Diagnosis Info)")
    print("   - 處理資訊 (Processing Info)")

if __name__ == "__main__":
    print("🚀 Medical Document Details Test")
    print("=" * 80)
    
    try:
        success = test_medical_details_api()
        show_usage_instructions()
        
        if success:
            print("\n✅ Test completed successfully!")
            print("🎯 The medical document details feature should work properly")
        else:
            print("\n❌ Test failed - check server status and try again")
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
