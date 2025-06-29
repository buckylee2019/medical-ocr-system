#!/usr/bin/env python3
"""
Create DynamoDB table for Medical OCR results
"""

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE')
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'medical-ocr-results')

def create_aws_session():
    if AWS_PROFILE:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        print(f"✅ Using AWS profile: {AWS_PROFILE}")
    else:
        session = boto3.Session(region_name=AWS_REGION)
        print("✅ Using default AWS credentials")
    return session

def create_dynamodb_table():
    """Create DynamoDB table for medical OCR results"""
    try:
        aws_session = create_aws_session()
        dynamodb = aws_session.resource('dynamodb')
        
        # Check if table already exists
        try:
            table = dynamodb.Table(TABLE_NAME)
            table.load()
            print(f"✅ Table '{TABLE_NAME}' already exists")
            return table
        except dynamodb.meta.client.exceptions.ResourceNotFoundException:
            pass
        
        # Create table
        print(f"🔨 Creating DynamoDB table: {TABLE_NAME}")
        
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'timestamp',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'processing_mode',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'timestamp-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                },
                {
                    'IndexName': 'processing-mode-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'processing_mode',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for table to be created
        print("⏳ Waiting for table to be created...")
        table.wait_until_exists()
        
        print(f"✅ Table '{TABLE_NAME}' created successfully!")
        print(f"📊 Table ARN: {table.table_arn}")
        
        return table
        
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        return None

def describe_table():
    """Describe the created table"""
    try:
        aws_session = create_aws_session()
        dynamodb = aws_session.resource('dynamodb')
        table = dynamodb.Table(TABLE_NAME)
        
        print(f"\n📋 Table Description: {TABLE_NAME}")
        print(f"Status: {table.table_status}")
        print(f"Item Count: {table.item_count}")
        print(f"Table Size: {table.table_size_bytes} bytes")
        print(f"Creation Date: {table.creation_date_time}")
        
        print("\n🔑 Key Schema:")
        for key in table.key_schema:
            print(f"  - {key['AttributeName']} ({key['KeyType']})")
        
        print("\n📊 Global Secondary Indexes:")
        if table.global_secondary_indexes:
            for gsi in table.global_secondary_indexes:
                print(f"  - {gsi['IndexName']}")
                for key in gsi['KeySchema']:
                    print(f"    - {key['AttributeName']} ({key['KeyType']})")
        else:
            print("  - None")
            
    except Exception as e:
        print(f"❌ Error describing table: {str(e)}")

if __name__ == "__main__":
    print("🚀 Medical OCR DynamoDB Table Setup")
    print("=" * 50)
    
    table = create_dynamodb_table()
    if table:
        describe_table()
        print(f"\n✅ Setup complete! Table '{TABLE_NAME}' is ready for use.")
        print(f"🔧 Make sure to set DYNAMODB_TABLE_NAME='{TABLE_NAME}' in your .env file")
    else:
        print("\n❌ Setup failed!")
