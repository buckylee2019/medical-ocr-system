#!/usr/bin/env python3
"""
Test DynamoDB connection and data conversion
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import save_to_dynamodb, convert_floats_to_decimal, dynamodb_table
from decimal import Decimal
import json

def test_float_conversion():
    """Test float to Decimal conversion"""
    print("🧪 Testing Float to Decimal Conversion")
    print("=" * 50)
    
    test_data = {
        "confidence_score": 0.85,
        "nested": {
            "accuracy": 0.92,
            "precision": 0.88
        },
        "scores": [0.1, 0.5, 0.9],
        "text": "sample text",
        "count": 42
    }
    
    print("📊 Original Data:")
    print(json.dumps(test_data, indent=2))
    
    converted_data = convert_floats_to_decimal(test_data)
    
    print("\n📊 Converted Data:")
    for key, value in converted_data.items():
        print(f"  - {key}: {value} ({type(value)})")
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                print(f"    - {nested_key}: {nested_value} ({type(nested_value)})")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                print(f"    - [{i}]: {item} ({type(item)})")
    
    return converted_data

def test_dynamodb_connection():
    """Test DynamoDB table connection"""
    print("\n🔗 Testing DynamoDB Connection")
    print("=" * 50)
    
    try:
        # Try to describe the table
        table_info = dynamodb_table.table_status
        print(f"✅ Table Status: {table_info}")
        print(f"📊 Table Name: {dynamodb_table.table_name}")
        print(f"🔑 Key Schema: {dynamodb_table.key_schema}")
        return True
    except Exception as e:
        print(f"❌ DynamoDB Connection Failed: {str(e)}")
        return False

def test_save_sample_data():
    """Test saving sample data to DynamoDB"""
    print("\n💾 Testing Sample Data Save")
    print("=" * 50)
    
    sample_data = {
        "certificate_info": {
            "certificate_no": "TEST-001",
            "certificate_date": "2024-01-01"
        },
        "patient_info": {
            "name": "測試病患",
            "sex": "男"
        }
    }
    
    try:
        result = save_to_dynamodb(
            data=sample_data,
            processing_mode='test',
            confidence_score=0.95,
            human_reviewed=False
        )
        
        if result['success']:
            print("✅ Sample Data Saved Successfully!")
            print(f"📋 Record ID: {result['record_id']}")
            print(f"⏰ Timestamp: {result['timestamp']}")
            return result['record_id']
        else:
            print(f"❌ Save Failed: {result['error']}")
            return None
            
    except Exception as e:
        print(f"❌ Save Exception: {str(e)}")
        return None

def test_retrieve_data(record_id):
    """Test retrieving data from DynamoDB"""
    print(f"\n📖 Testing Data Retrieval for ID: {record_id}")
    print("=" * 50)
    
    try:
        response = dynamodb_table.get_item(Key={'id': record_id})
        
        if 'Item' in response:
            item = response['Item']
            print("✅ Data Retrieved Successfully!")
            print(f"📊 Processing Mode: {item.get('processing_mode')}")
            print(f"🎯 Confidence Score: {item.get('confidence_score')} ({type(item.get('confidence_score'))})")
            print(f"👤 Human Reviewed: {item.get('human_reviewed')}")
            print(f"📋 Data Keys: {list(item.get('data', {}).keys())}")
            return True
        else:
            print("❌ No item found with that ID")
            return False
            
    except Exception as e:
        print(f"❌ Retrieval Failed: {str(e)}")
        return False

def cleanup_test_data(record_id):
    """Clean up test data"""
    print(f"\n🧹 Cleaning up test data: {record_id}")
    print("=" * 50)
    
    try:
        dynamodb_table.delete_item(Key={'id': record_id})
        print("✅ Test data cleaned up successfully")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {str(e)}")

if __name__ == "__main__":
    print("🚀 DynamoDB Integration Test")
    print("=" * 80)
    
    # Test float conversion
    converted_data = test_float_conversion()
    
    # Test DynamoDB connection
    if test_dynamodb_connection():
        # Test saving data
        record_id = test_save_sample_data()
        
        if record_id:
            # Test retrieving data
            if test_retrieve_data(record_id):
                print("\n✅ All tests passed!")
            
            # Cleanup
            cleanup_test_data(record_id)
        else:
            print("\n❌ Save test failed, skipping retrieval test")
    else:
        print("\n❌ DynamoDB connection failed, skipping data tests")
        print("\n💡 Make sure to:")
        print("1. Run 'python create_dynamodb_table.py' first")
        print("2. Check your AWS credentials")
        print("3. Verify the table name in .env file")
