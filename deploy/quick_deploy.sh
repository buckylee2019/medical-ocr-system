#!/bin/bash

# Quick AWS Deployment Script for Medical OCR System
# This script helps set up the basic AWS resources needed

set -e

echo "🏥 Medical OCR AWS Quick Deploy"
echo "================================"

# Configuration
APP_NAME="medical-ocr-app"
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="medical-ocr-${ACCOUNT_ID}"
TABLE_NAME="medical-ocr-data"

echo "📋 Configuration:"
echo "  App Name: $APP_NAME"
echo "  Region: $REGION"
echo "  Account ID: $ACCOUNT_ID"
echo "  S3 Bucket: $BUCKET_NAME"
echo "  DynamoDB Table: $TABLE_NAME"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi

echo "✅ AWS CLI and credentials configured"

# Create S3 bucket
echo "🪣 Creating S3 bucket..."
if aws s3 ls "s3://$BUCKET_NAME" 2>&1 | grep -q 'NoSuchBucket'; then
    if [ "$REGION" = "us-east-1" ]; then
        aws s3 mb "s3://$BUCKET_NAME"
    else
        aws s3 mb "s3://$BUCKET_NAME" --region "$REGION"
    fi
    echo "✅ S3 bucket created: $BUCKET_NAME"
else
    echo "✅ S3 bucket already exists: $BUCKET_NAME"
fi

# Configure S3 CORS
echo "🔧 Configuring S3 CORS..."
cat > /tmp/cors.json << EOF
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "POST", "PUT", "DELETE"],
            "AllowedOrigins": ["*"],
            "MaxAgeSeconds": 3000
        }
    ]
}
EOF

aws s3api put-bucket-cors --bucket "$BUCKET_NAME" --cors-configuration file:///tmp/cors.json
echo "✅ S3 CORS configured"

# Create DynamoDB table
echo "🗄️ Creating DynamoDB table..."
if ! aws dynamodb describe-table --table-name "$TABLE_NAME" &> /dev/null; then
    cd ..
    python create_dynamodb_table.py
    echo "✅ DynamoDB table created: $TABLE_NAME"
else
    echo "✅ DynamoDB table already exists: $TABLE_NAME"
fi

# Create IAM role for App Runner
echo "🔐 Creating IAM role..."
ROLE_NAME="${APP_NAME}-role"

# Trust policy for App Runner
cat > /tmp/trust-policy.json << EOF
{
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
EOF

# Permission policy
cat > /tmp/permission-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Scan",
                "dynamodb:Query"
            ],
            "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": "arn:aws:s3:::${BUCKET_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Create role if it doesn't exist
if ! aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document file:///tmp/trust-policy.json
    aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "${APP_NAME}-policy" --policy-document file:///tmp/permission-policy.json
    echo "✅ IAM role created: $ROLE_NAME"
else
    echo "✅ IAM role already exists: $ROLE_NAME"
fi

# Create App Runner configuration
echo "📝 Creating App Runner configuration..."
cat > apprunner.yaml << EOF
version: 1.0
runtime: python3
build:
  commands:
    build:
      - echo "Installing dependencies"
      - pip install -r requirements.txt
run:
  runtime-version: 3.11
  command: python app.py
  network:
    port: 5006
  env:
    - name: AWS_DEFAULT_REGION
      value: $REGION
    - name: DYNAMODB_TABLE_NAME
      value: $TABLE_NAME
    - name: S3_BUCKET
      value: $BUCKET_NAME
    - name: FLASK_ENV
      value: production
EOF

echo "✅ App Runner configuration created"

# Clean up temp files
rm -f /tmp/cors.json /tmp/trust-policy.json /tmp/permission-policy.json

echo ""
echo "🎉 AWS Resources Setup Complete!"
echo "================================"
echo ""
echo "📋 Created Resources:"
echo "  ✅ S3 Bucket: $BUCKET_NAME"
echo "  ✅ DynamoDB Table: $TABLE_NAME"
echo "  ✅ IAM Role: $ROLE_NAME"
echo "  ✅ App Runner Config: apprunner.yaml"
echo ""
echo "🚀 Next Steps:"
echo "1. Push your code to GitHub repository"
echo "2. Go to AWS App Runner console"
echo "3. Create new service from GitHub repository"
echo "4. Use the generated apprunner.yaml configuration"
echo "5. Set the IAM role: arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo ""
echo "🔗 Useful Links:"
echo "  AWS App Runner Console: https://console.aws.amazon.com/apprunner/"
echo "  S3 Console: https://console.aws.amazon.com/s3/"
echo "  DynamoDB Console: https://console.aws.amazon.com/dynamodb/"
echo ""
echo "💡 Test your deployment:"
echo "  Health Check: https://your-app-url/health"
echo "  Main App: https://your-app-url/"
