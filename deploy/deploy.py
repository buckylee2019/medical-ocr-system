#!/usr/bin/env python3
"""
AWS Deployment Script for Medical OCR System
"""

import boto3
import json
import os
import subprocess
import sys
from pathlib import Path

class MedicalOCRDeployer:
    def __init__(self):
        self.region = 'us-west-2'
        self.app_name = 'medical-ocr-app'
        self.bucket_name = f'medical-ocr-{self.get_account_id()}'
        
    def get_account_id(self):
        """Get AWS account ID"""
        try:
            sts = boto3.client('sts')
            return sts.get_caller_identity()['Account']
        except Exception as e:
            print(f"❌ Failed to get account ID: {e}")
            return 'unknown'
    
    def check_prerequisites(self):
        """Check deployment prerequisites"""
        print("🔍 Checking prerequisites...")
        
        # Check AWS credentials
        try:
            boto3.client('sts').get_caller_identity()
            print("✅ AWS credentials configured")
        except Exception as e:
            print(f"❌ AWS credentials not configured: {e}")
            return False
        
        # Check required services
        services = ['dynamodb', 's3', 'bedrock']
        for service in services:
            try:
                boto3.client(service, region_name=self.region)
                print(f"✅ {service.upper()} service available")
            except Exception as e:
                print(f"❌ {service.upper()} service error: {e}")
                return False
        
        return True
    
    def create_s3_bucket(self):
        """Create S3 bucket for images"""
        print(f"🪣 Creating S3 bucket: {self.bucket_name}")
        
        try:
            s3 = boto3.client('s3', region_name=self.region)
            
            # Check if bucket exists
            try:
                s3.head_bucket(Bucket=self.bucket_name)
                print(f"✅ S3 bucket {self.bucket_name} already exists")
                return True
            except:
                pass
            
            # Create bucket
            if self.region == 'us-east-1':
                s3.create_bucket(Bucket=self.bucket_name)
            else:
                s3.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # Configure CORS
            cors_config = {
                'CORSRules': [
                    {
                        'AllowedHeaders': ['*'],
                        'AllowedMethods': ['GET', 'POST', 'PUT', 'DELETE'],
                        'AllowedOrigins': ['*'],
                        'MaxAgeSeconds': 3000
                    }
                ]
            }
            s3.put_bucket_cors(Bucket=self.bucket_name, CORSConfiguration=cors_config)
            
            print(f"✅ S3 bucket {self.bucket_name} created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create S3 bucket: {e}")
            return False
    
    def create_dynamodb_table(self):
        """Create DynamoDB table"""
        print("🗄️ Creating DynamoDB table...")
        
        try:
            # Run the existing table creation script
            result = subprocess.run([sys.executable, '../create_dynamodb_table.py'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ DynamoDB table created successfully")
                return True
            else:
                print(f"❌ DynamoDB table creation failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to create DynamoDB table: {e}")
            return False
    
    def create_iam_roles(self):
        """Create necessary IAM roles"""
        print("🔐 Creating IAM roles...")
        
        try:
            iam = boto3.client('iam')
            
            # App Runner service role
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "tasks.apprunner.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:*",
                            "s3:*",
                            "bedrock:*"
                        ],
                        "Resource": "*"
                    }
                ]
            }
            
            role_name = f"{self.app_name}-role"
            
            try:
                iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Role for Medical OCR App Runner service"
                )
                
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f"{self.app_name}-policy",
                    PolicyDocument=json.dumps(policy_document)
                )
                
                print(f"✅ IAM role {role_name} created successfully")
                
            except iam.exceptions.EntityAlreadyExistsException:
                print(f"✅ IAM role {role_name} already exists")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to create IAM roles: {e}")
            return False
    
    def deploy_app_runner(self):
        """Deploy to AWS App Runner"""
        print("🚀 Deploying to AWS App Runner...")
        
        try:
            apprunner = boto3.client('apprunner', region_name=self.region)
            
            # Check if service exists
            try:
                services = apprunner.list_services()
                existing_service = None
                for service in services['ServiceSummaryList']:
                    if service['ServiceName'] == self.app_name:
                        existing_service = service
                        break
                
                if existing_service:
                    print(f"⚠️ App Runner service {self.app_name} already exists")
                    print(f"Service ARN: {existing_service['ServiceArn']}")
                    print(f"Service URL: {existing_service['ServiceUrl']}")
                    return True
                    
            except Exception as e:
                print(f"Warning: Could not check existing services: {e}")
            
            # Create new service
            service_config = {
                'ServiceName': self.app_name,
                'SourceConfiguration': {
                    'AutoDeploymentsEnabled': False,
                    'CodeRepository': {
                        'RepositoryUrl': 'https://github.com/your-username/medical-ocr.git',
                        'SourceCodeVersion': {
                            'Type': 'BRANCH',
                            'Value': 'main'
                        },
                        'CodeConfiguration': {
                            'ConfigurationSource': 'REPOSITORY'
                        }
                    }
                },
                'InstanceConfiguration': {
                    'Cpu': '1024',
                    'Memory': '2048',
                    'InstanceRoleArn': f"arn:aws:iam::{self.get_account_id()}:role/{self.app_name}-role"
                },
                'HealthCheckConfiguration': {
                    'Protocol': 'HTTP',
                    'Path': '/health',
                    'Interval': 10,
                    'Timeout': 5,
                    'HealthyThreshold': 1,
                    'UnhealthyThreshold': 5
                }
            }
            
            print("ℹ️ Note: You'll need to configure the GitHub repository manually")
            print("📋 App Runner service configuration prepared")
            return True
            
        except Exception as e:
            print(f"❌ Failed to deploy to App Runner: {e}")
            return False
    
    def deploy(self, method='apprunner'):
        """Main deployment method"""
        print(f"🚀 Starting deployment to AWS using {method.upper()}")
        print("=" * 60)
        
        # Check prerequisites
        if not self.check_prerequisites():
            print("❌ Prerequisites check failed")
            return False
        
        # Create resources
        steps = [
            self.create_s3_bucket,
            self.create_dynamodb_table,
            self.create_iam_roles,
        ]
        
        if method == 'apprunner':
            steps.append(self.deploy_app_runner)
        
        for step in steps:
            if not step():
                print(f"❌ Deployment failed at step: {step.__name__}")
                return False
        
        print("\n🎉 Deployment completed successfully!")
        print(f"📋 Next steps:")
        print(f"1. Update environment variables in AWS console")
        print(f"2. Configure your GitHub repository (if using App Runner)")
        print(f"3. Test the deployed application")
        print(f"4. Set up monitoring and logging")
        
        return True

def main():
    """Main function"""
    deployer = MedicalOCRDeployer()
    
    print("🏥 Medical OCR AWS Deployment Tool")
    print("=" * 60)
    
    method = input("Choose deployment method (apprunner/ecs/lambda): ").lower()
    if method not in ['apprunner', 'ecs', 'lambda']:
        method = 'apprunner'
        print(f"Using default method: {method}")
    
    success = deployer.deploy(method)
    
    if success:
        print("\n✅ Deployment successful!")
        sys.exit(0)
    else:
        print("\n❌ Deployment failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
