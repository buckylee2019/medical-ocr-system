#!/usr/bin/env python3
"""
Test script for image management functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import (
    save_image_metadata_to_dynamodb, 
    update_image_processing_status,
    get_uploaded_images,
    convert_floats_to_decimal,
    save_to_dynamodb
)
from decimal import Decimal
import json

def test_convert_floats():
    """Test float to decimal conversion"""
    print("🧪 Testing Float to Decimal Conversion")
    print("=" * 50)
    
    test_data = {
        "confidence": 0.95,
        "scores": [0.1, 0.5, 0.9],
        "nested": {
            "accuracy": 0.88,
            "precision": 0.92
        },
        "text": "sample",
        "count": 42
    }
    
    converted = convert_floats_to_decimal(test_data)
    
    print("✅ Conversion successful!")
    print(f"Original confidence: {test_data['confidence']} ({type(test_data['confidence'])})")
    print(f"Converted confidence: {converted['confidence']} ({type(converted['confidence'])})")
    
    return True

def test_image_metadata_save():
    """Test saving image metadata"""
    print("\n💾 Testing Image Metadata Save")
    print("=" * 50)
    
    try:
        result = save_image_metadata_to_dynamodb(
            filename="test_image.jpg",
            s3_key="test/2025/06/29/test_image.jpg",
            file_size=1024000,
            content_type="image/jpeg",
            session_id="test-session-123"
        )
        
        if result['success']:
            print("✅ Image metadata saved successfully!")
            print(f"📋 Image ID: {result['image_id']}")
            return result['image_id']
        else:
            print(f"❌ Save failed: {result['error']}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None

def test_status_update(image_id):
    """Test updating image processing status"""
    print(f"\n🔄 Testing Status Update for ID: {image_id}")
    print("=" * 50)
    
    try:
        # Test updating to processing
        result = update_image_processing_status(image_id, 'processing')
        if result['success']:
            print("✅ Status updated to 'processing'")
        
        # Test updating to completed with OCR result ID
        ocr_result = save_to_dynamodb(
            data={"test": "ocr_result"},
            processing_mode="test",
            confidence_score=0.95,
            human_reviewed=False
        )
        
        if ocr_result['success']:
            result = update_image_processing_status(image_id, 'completed', ocr_result['record_id'])
            if result['success']:
                print("✅ Status updated to 'completed' with OCR result ID")
                return ocr_result['record_id']
        
        return None
        
    except Exception as e:
        print(f"❌ Status update failed: {str(e)}")
        return None

def test_get_images():
    """Test getting uploaded images list"""
    print("\n📋 Testing Get Images List")
    print("=" * 50)
    
    try:
        result = get_uploaded_images(limit=10)
        
        if result['success']:
            print(f"✅ Retrieved {result['count']} images")
            for i, image in enumerate(result['images'][:3]):  # Show first 3
                print(f"  {i+1}. {image['filename']} - {image['processing_status']}")
            return True
        else:
            print(f"❌ Failed to get images: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def cleanup_test_data(image_id, ocr_result_id):
    """Clean up test data"""
    print(f"\n🧹 Cleaning up test data")
    print("=" * 50)
    
    try:
        from app import dynamodb_table
        
        # Delete image metadata
        if image_id:
            dynamodb_table.delete_item(Key={'id': image_id})
            print(f"✅ Deleted image metadata: {image_id}")
        
        # Delete OCR result
        if ocr_result_id:
            dynamodb_table.delete_item(Key={'id': ocr_result_id})
            print(f"✅ Deleted OCR result: {ocr_result_id}")
            
    except Exception as e:
        print(f"⚠️ Cleanup warning: {str(e)}")

if __name__ == "__main__":
    print("🚀 Image Management System Test")
    print("=" * 80)
    
    image_id = None
    ocr_result_id = None
    
    try:
        # Test float conversion
        if test_convert_floats():
            # Test image metadata save
            image_id = test_image_metadata_save()
            
            if image_id:
                # Test status update
                ocr_result_id = test_status_update(image_id)
                
                # Test get images
                test_get_images()
                
                print("\n✅ All tests passed!")
            else:
                print("\n❌ Image metadata save failed, skipping other tests")
        else:
            print("\n❌ Float conversion test failed")
            
    finally:
        # Always try to cleanup
        cleanup_test_data(image_id, ocr_result_id)
        
    print("\n💡 Next steps:")
    print("1. Start the application: python app.py")
    print("2. Visit http://localhost:5006 to upload images")
    print("3. Visit http://localhost:5006/images to manage images")
    print("4. Test the complete workflow")
