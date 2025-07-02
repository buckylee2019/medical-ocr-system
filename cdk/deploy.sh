#!/bin/bash

# RPA OCR ECS Fargate Deployment Script

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
    echo "  -r, --region REGION      AWS region to deploy to (optional, defaults to profile region or us-west-2)"
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

echo "🚀 Starting RPA OCR ECS Fargate deployment..."

# Set up AWS CLI commands with profile if specified
AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
    echo "📋 Using AWS profile: $AWS_PROFILE"
fi

# Check if AWS CLI is configured
if ! $AWS_CMD sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI is not configured or credentials are invalid"
    if [ ! -z "$AWS_PROFILE" ]; then
        echo "Please check your AWS profile '$AWS_PROFILE' configuration"
    else
        echo "Please run 'aws configure' or set up your AWS credentials"
    fi
    exit 1
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

echo "📋 Deployment Info:"
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

# Install CDK dependencies if not already installed
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# Bootstrap CDK if needed
echo "🔧 Checking CDK bootstrap status..."
if ! $AWS_CMD cloudformation describe-stacks --stack-name CDKToolkit --region $REGION > /dev/null 2>&1; then
    echo "🔧 Bootstrapping CDK..."
    if [ ! -z "$AWS_PROFILE" ]; then
        cdk bootstrap aws://$ACCOUNT/$REGION --profile $AWS_PROFILE
    else
        cdk bootstrap aws://$ACCOUNT/$REGION
    fi
else
    echo "✅ CDK already bootstrapped"
fi

# Synthesize the stack
echo "🔨 Synthesizing CDK stack..."
if [ ! -z "$AWS_PROFILE" ]; then
    cdk synth --profile $AWS_PROFILE
else
    cdk synth
fi

# Deploy the stack
echo "🚀 Deploying RPA OCR ECS stack..."
if [ ! -z "$AWS_PROFILE" ]; then
    cdk deploy --require-approval never --profile $AWS_PROFILE
else
    cdk deploy --require-approval never
fi

echo "✅ Deployment completed!"
echo ""
echo "📋 Next steps:"
echo "1. Check the CloudFormation outputs for the Load Balancer DNS name"
echo "2. Wait a few minutes for the service to become healthy"
echo "3. Access your application via the Load Balancer URL"
echo ""
echo "🔍 To check deployment status:"
if [ ! -z "$AWS_PROFILE" ]; then
    echo "   aws --profile $AWS_PROFILE ecs describe-services --cluster rpa-ocr-cluster --services rpa-ocr-service --region $REGION"
else
    echo "   aws ecs describe-services --cluster rpa-ocr-cluster --services rpa-ocr-service --region $REGION"
fi
echo ""
echo "📊 To view logs:"
if [ ! -z "$AWS_PROFILE" ]; then
    echo "   aws --profile $AWS_PROFILE logs tail /ecs/rpa-ocr --follow --region $REGION"
else
    echo "   aws logs tail /ecs/rpa-ocr --follow --region $REGION"
fi
