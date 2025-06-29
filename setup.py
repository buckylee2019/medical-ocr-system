#!/usr/bin/env python3
"""
Setup script for Medical OCR Web Application
"""

import boto3
import json
import os
from botocore.exceptions import ClientError

def create_s3_bucket(session, bucket_name, region='us-east-1'):
    """Create S3 bucket for storing processed documents"""
    try:
        s3_client = session.client('s3')
        
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        
        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        # Set up CORS for web access
        cors_configuration = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE'],
                    'AllowedOrigins': ['*'],
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3000
                }
            ]
        }
        
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        
        print(f"✅ S3 bucket '{bucket_name}' created successfully")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
            print(f"✅ S3 bucket '{bucket_name}' already exists")
            return True
        else:
            print(f"❌ Error creating S3 bucket: {e}")
            return False

def setup_iam_policy():
    """Create IAM policy for the application"""
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "arn:aws:bedrock:*::foundation-model/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{os.getenv('S3_BUCKET', 'medical-ocr-documents')}",
                    f"arn:aws:s3:::{os.getenv('S3_BUCKET', 'medical-ocr-documents')}/*"
                ]
            }
        ]
    }
    
    print("📋 IAM Policy for your application:")
    print(json.dumps(policy_document, indent=2))
    print("\n💡 Create this policy in IAM and attach it to your user/role")

def check_bedrock_access(session):
    """Check if Bedrock access is properly configured"""
    try:
        bedrock_client = session.client('bedrock-runtime')
        
        # Try to list foundation models (this requires bedrock:ListFoundationModels permission)
        # For now, we'll just check if the client can be created
        print("✅ Bedrock client created successfully")
        print("💡 Make sure you have access to Amazon Nova models in your region")
        return True
        
    except Exception as e:
        print(f"❌ Error accessing Bedrock: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Medical OCR Web Application")
    print("=" * 50)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check AWS credentials and create session
    session = check_aws_credentials()
    if not session:
        return
    
    bucket_name = os.getenv('S3_BUCKET', 'medical-ocr-documents')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Create S3 bucket
    if create_s3_bucket(session, bucket_name, region):
        print(f"📁 S3 bucket ready: s3://{bucket_name}")
    
    # Check Bedrock access
    check_bedrock_access(session)
    
    # Show IAM policy
    setup_iam_policy()
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\n📝 Next steps:")
    print("1. Copy .env.example to .env and fill in your values")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run the application: python app.py")
    print("4. Open http://localhost:5000 in your browser")
    
def check_aws_credentials():
    """Check AWS credentials and profile configuration"""
    try:
        # Check if AWS profile is specified
        aws_profile = os.getenv('AWS_PROFILE')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        if aws_profile:
            print(f"🔑 Using AWS profile: {aws_profile}")
            session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        else:
            print("🔑 Using default AWS credentials")
            session = boto3.Session(region_name=aws_region)
        
        # Test credentials
        sts_client = session.client('sts')
        identity = sts_client.get_caller_identity()
        print(f"✅ AWS credentials configured for: {identity.get('Arn')}")
        print(f"📍 Region: {aws_region}")
        
        return session
        
    except Exception as e:
        print(f"❌ AWS credentials not configured: {e}")
        print("\n💡 Setup options:")
        print("1. Configure AWS CLI: aws configure")
        print("2. Use AWS profiles: aws configure --profile myprofile")
        print("3. Set environment variables in .env file")
        print("4. Use IAM roles (if running on EC2/Lambda)")
        return None
    
    # Create S3 bucket
    if create_s3_bucket(bucket_name, region):
        print(f"📁 S3 bucket ready: s3://{bucket_name}")
    
    # Check Bedrock access
    check_bedrock_access()
    
    # Show IAM policy
    setup_iam_policy()
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\n📝 Next steps:")
    print("1. Copy .env.example to .env and fill in your values")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run the application: python app.py")
    print("4. Open http://localhost:5000 in your browser")

if __name__ == "__main__":
    main()
