#!/usr/bin/env python3
"""
Test script for pending review workflow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import (
    save_image_metadata_to_dynamodb, 
    update_image_processing_status,
    get_uploaded_images,
    s3_client,
    S3_BUCKET
)
import json
from datetime import datetime

def create_test_pending_review():
    """創建一個測試的待審核圖片"""
    print("🧪 Creating Test Pending Review Image")
    print("=" * 50)
    
    try:
        # 創建測試圖片元數據
        session_id = f"test-pending-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        filename = "test_pending_review.jpg"
        s3_key = f"human_review_uploads/{datetime.now().strftime('%Y/%m/%d')}/{session_id}/{filename}"
        
        # 模擬圖片數據
        test_image_data = b"fake_image_data_for_testing"
        
        # 上傳到 S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=test_image_data,
            ContentType="image/jpeg",
            Metadata={
                'session_id': session_id,
                'processing_mode': 'human_review',
                'original_filename': filename
            }
        )
        print(f"✅ Test image uploaded to S3: {s3_key}")
        
        # 保存圖片元數據
        image_metadata = save_image_metadata_to_dynamodb(
            filename=filename,
            s3_key=s3_key,
            file_size=len(test_image_data),
            content_type="image/jpeg",
            session_id=session_id
        )
        
        if not image_metadata['success']:
            print(f"❌ Failed to save metadata: {image_metadata['error']}")
            return None
        
        image_id = image_metadata['image_id']
        print(f"✅ Image metadata saved: {image_id}")
        
        # 更新狀態為待審核
        update_result = update_image_processing_status(image_id, 'pending_review')
        if update_result['success']:
            print("✅ Status updated to 'pending_review'")
        else:
            print(f"❌ Failed to update status: {update_result.get('error', 'Unknown error')}")
        
        # 創建待審核結果到 S3
        pending_key = f"pending_review/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        claude_result = {
            'success': True,
            'extracted_data': {
                'certificate_info': {
                    'certificate_no': 'TEST-PENDING-001',
                    'certificate_date': '2024-01-01'
                },
                'patient_info': {
                    'name': '測試待審核病患',
                    'sex': '男'
                }
            }
        }
        
        pending_data = {
            'session_id': session_id,
            'image_id': image_id,
            'filename': filename,
            'processed_at': datetime.now().isoformat(),
            'processing_mode': 'human_review',
            'status': 'pending_review',
            'claude_result': claude_result
        }
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=pending_key,
            Body=json.dumps(pending_data, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        print(f"✅ Pending review data saved to S3: {pending_key}")
        
        return {
            'image_id': image_id,
            'session_id': session_id,
            'filename': filename,
            's3_key': s3_key,
            'pending_key': pending_key
        }
        
    except Exception as e:
        print(f"❌ Error creating test data: {str(e)}")
        return None

def test_get_pending_images():
    """測試獲取待審核圖片列表"""
    print("\n📋 Testing Get Pending Review Images")
    print("=" * 50)
    
    try:
        result = get_uploaded_images(limit=20)
        
        if result['success']:
            pending_images = [img for img in result['images'] if img['processing_status'] == 'pending_review']
            print(f"✅ Found {len(pending_images)} pending review images")
            
            for img in pending_images:
                print(f"  - {img['filename']} (ID: {img['id'][:8]}...)")
                print(f"    Status: {img['processing_status']}")
                print(f"    Session: {img.get('session_id', 'N/A')}")
                print(f"    Created: {img['created_at']}")
            
            return pending_images
        else:
            print(f"❌ Failed to get images: {result['error']}")
            return []
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return []

def test_review_api(image_id):
    """測試審核API"""
    print(f"\n🔍 Testing Review API for Image: {image_id}")
    print("=" * 50)
    
    try:
        # 這裡我們模擬 API 調用的邏輯
        from app import dynamodb_table
        
        # 獲取圖片信息
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            print("❌ Image not found")
            return False
        
        image_item = response['Item']
        print(f"✅ Image found: {image_item['filename']}")
        print(f"  Status: {image_item['processing_status']}")
        print(f"  Session ID: {image_item.get('session_id', 'N/A')}")
        
        if image_item.get('processing_status') == 'pending_review':
            print("✅ Image is in pending_review status - ready for review")
            print(f"🔗 Review URL: http://localhost:5006/review/{image_id}")
            return True
        else:
            print(f"⚠️ Image status is '{image_item.get('processing_status')}', not 'pending_review'")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def cleanup_test_data(test_data):
    """清理測試數據"""
    if not test_data:
        return
    
    print(f"\n🧹 Cleaning up test data")
    print("=" * 50)
    
    try:
        from app import dynamodb_table
        
        # 刪除 DynamoDB 記錄
        dynamodb_table.delete_item(Key={'id': test_data['image_id']})
        print(f"✅ Deleted DynamoDB record: {test_data['image_id']}")
        
        # 刪除 S3 文件
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=test_data['s3_key'])
            print(f"✅ Deleted S3 image: {test_data['s3_key']}")
        except:
            print(f"⚠️ Could not delete S3 image: {test_data['s3_key']}")
        
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=test_data['pending_key'])
            print(f"✅ Deleted S3 pending data: {test_data['pending_key']}")
        except:
            print(f"⚠️ Could not delete S3 pending data: {test_data['pending_key']}")
            
    except Exception as e:
        print(f"⚠️ Cleanup warning: {str(e)}")

if __name__ == "__main__":
    print("🚀 Pending Review Workflow Test")
    print("=" * 80)
    
    test_data = None
    
    try:
        # 創建測試待審核圖片
        test_data = create_test_pending_review()
        
        if test_data:
            # 測試獲取待審核圖片列表
            pending_images = test_get_pending_images()
            
            # 測試審核API
            test_review_api(test_data['image_id'])
            
            print("\n✅ All tests completed!")
            print("\n💡 Next steps:")
            print("1. Start the application: python app.py")
            print("2. Visit http://localhost:5006/images")
            print("3. Look for the test image with 'pending_review' status")
            print("4. Click '進入審核' button to test the review workflow")
            print(f"5. Or directly visit: http://localhost:5006/review/{test_data['image_id']}")
        else:
            print("\n❌ Test data creation failed")
            
    finally:
        # 詢問是否清理測試數據
        if test_data:
            cleanup_choice = input("\n🤔 Do you want to clean up test data? (y/N): ").lower()
            if cleanup_choice == 'y':
                cleanup_test_data(test_data)
            else:
                print("📝 Test data preserved for manual testing")
                print(f"   Image ID: {test_data['image_id']}")
                print(f"   Review URL: http://localhost:5006/review/{test_data['image_id']}")
