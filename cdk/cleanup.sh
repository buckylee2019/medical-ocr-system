#!/bin/bash

# RPA OCR ECS Fargate Cleanup Script

set -e

# Parse command line arguments
AWS_PROFILE=""
REGION=""

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --profile PROFILE    AWS profile to use (optional)"
    echo "  -r, --region REGION      AWS region (optional, defaults to profile region or us-west-2)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Use default profile and region"
    echo "  $0 -p my-profile            # Use specific AWS profile"
    echo "  $0 -p my-profile -r us-east-1  # Use specific profile and region"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

echo "🧹 Starting RPA OCR ECS stack cleanup..."

# Set up AWS CLI commands with profile if specified
AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
    echo "📋 Using AWS profile: $AWS_PROFILE"
fi

# Get AWS account and region
ACCOUNT=$($AWS_CMD sts get-caller-identity --query Account --output text)

# Determine region
if [ -z "$REGION" ]; then
    if [ ! -z "$AWS_PROFILE" ]; then
        REGION=$($AWS_CMD configure get region || echo "us-west-2")
    else
        REGION=$(aws configure get region || echo "us-west-2")
    fi
fi

echo "📋 Cleanup Info:"
echo "   Account: $ACCOUNT"
echo "   Region: $REGION"
if [ ! -z "$AWS_PROFILE" ]; then
    echo "   Profile: $AWS_PROFILE"
fi

# Set CDK environment variables
export CDK_DEFAULT_ACCOUNT=$ACCOUNT
export CDK_DEFAULT_REGION=$REGION

# Set AWS profile for CDK if specified
if [ ! -z "$AWS_PROFILE" ]; then
    export AWS_PROFILE=$AWS_PROFILE
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "🗑️  Destroying RPA OCR ECS stack..."
if [ ! -z "$AWS_PROFILE" ]; then
    cdk destroy --force --profile $AWS_PROFILE
else
    cdk destroy --force
fi

echo "✅ Cleanup completed!"
echo ""
echo "📋 Manual cleanup (if needed):"
echo "1. Check for any remaining ECR repositories"
echo "2. Verify S3 buckets are cleaned up"
echo "3. Check CloudWatch log groups"
