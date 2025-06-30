#!/bin/bash

# Medical OCR System - Container Deployment Script
set -e

echo "🐳 Medical OCR System - Container Deployment"
echo "============================================="

# Configuration
STACK_NAME="medical-ocr-stack"
REGION="us-west-2"
APP_NAME="medical-ocr-app"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "📋 Configuration:"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $REGION"
echo "  App Name: $APP_NAME"
echo "  Account ID: $ACCOUNT_ID"
echo ""

# Step 1: Deploy CloudFormation Stack
echo "🚀 Step 1: Deploying CloudFormation Infrastructure..."
aws cloudformation deploy \
    --template-file cloudformation/medical-ocr-infrastructure.yaml \
    --stack-name $STACK_NAME \
    --parameter-overrides AppName=$APP_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

if [ $? -eq 0 ]; then
    echo "✅ CloudFormation stack deployed successfully"
else
    echo "❌ CloudFormation deployment failed"
    exit 1
fi

# Get ECR repository URI from CloudFormation outputs
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text)

echo "📦 ECR Repository: $ECR_URI"

# Step 2: Build and Push Docker Image
echo ""
echo "🐳 Step 2: Building and pushing Docker image..."

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t $APP_NAME .

# Tag image for ECR
docker tag $APP_NAME:latest $ECR_URI:latest

# Push image to ECR
echo "📤 Pushing image to ECR..."
docker push $ECR_URI:latest

if [ $? -eq 0 ]; then
    echo "✅ Docker image pushed successfully"
else
    echo "❌ Docker push failed"
    exit 1
fi

# Step 3: Update App Runner Service
echo ""
echo "🔄 Step 3: Updating App Runner service..."

# Get App Runner Service ARN
SERVICE_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceArn`].OutputValue' \
    --output text)

# Trigger deployment
aws apprunner start-deployment \
    --service-arn $SERVICE_ARN \
    --region $REGION

if [ $? -eq 0 ]; then
    echo "✅ App Runner deployment started"
else
    echo "❌ App Runner deployment failed"
    exit 1
fi

# Step 4: Get deployment status and URL
echo ""
echo "📊 Step 4: Getting deployment information..."

SERVICE_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceUrl`].OutputValue' \
    --output text)

S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
    --output text)

DYNAMODB_TABLE=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`DynamoDBTableName`].OutputValue' \
    --output text)

echo ""
echo "🎉 Deployment Completed Successfully!"
echo "====================================="
echo ""
echo "🔗 Application URL: $SERVICE_URL"
echo "🪣 S3 Bucket: $S3_BUCKET"
echo "🗄️ DynamoDB Table: $DYNAMODB_TABLE"
echo "📦 ECR Repository: $ECR_URI"
echo ""
echo "🧪 Test Endpoints:"
echo "  Health Check: $SERVICE_URL/health"
echo "  Main App: $SERVICE_URL/"
echo "  Image Management: $SERVICE_URL/images"
echo ""
echo "📊 Monitor Deployment:"
echo "  aws apprunner describe-service --service-arn $SERVICE_ARN --region $REGION"
echo ""
echo "💡 Next Steps:"
echo "  1. Wait for App Runner deployment to complete (5-10 minutes)"
echo "  2. Test the health check endpoint"
echo "  3. Upload and process medical documents"
echo "  4. Monitor CloudWatch logs for any issues"
