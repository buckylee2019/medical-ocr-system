#!/bin/bash

# RPA OCR ECS Status Check Script

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

# Set up AWS CLI commands with profile if specified
AWS_CMD="aws"
if [ ! -z "$AWS_PROFILE" ]; then
    AWS_CMD="aws --profile $AWS_PROFILE"
fi

# Determine region
if [ -z "$REGION" ]; then
    if [ ! -z "$AWS_PROFILE" ]; then
        REGION=$($AWS_CMD configure get region || echo "us-west-2")
    else
        REGION=$(aws configure get region || echo "us-west-2")
    fi
fi

echo "🔍 RPA OCR ECS Service Status"
echo "================================"
if [ ! -z "$AWS_PROFILE" ]; then
    echo "AWS Profile: $AWS_PROFILE"
fi
echo "Region: $REGION"
echo ""

# Check if stack exists
if $AWS_CMD cloudformation describe-stacks --stack-name RpaOcrEcsStack --region $REGION > /dev/null 2>&1; then
    echo "✅ CloudFormation Stack: EXISTS"
    
    # Get stack outputs
    echo ""
    echo "📋 Stack Outputs:"
    $AWS_CMD cloudformation describe-stacks --stack-name RpaOcrEcsStack --region $REGION \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output table
    
    # Check ECS service status
    echo ""
    echo "🚀 ECS Service Status:"
    $AWS_CMD ecs describe-services --cluster rpa-ocr-cluster --services rpa-ocr-service --region $REGION \
        --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}' --output table
    
    # Check task health
    echo ""
    echo "💊 Task Health:"
    TASK_ARNS=$($AWS_CMD ecs list-tasks --cluster rpa-ocr-cluster --service-name rpa-ocr-service --region $REGION --query 'taskArns' --output text)
    
    if [ ! -z "$TASK_ARNS" ]; then
        $AWS_CMD ecs describe-tasks --cluster rpa-ocr-cluster --tasks $TASK_ARNS --region $REGION \
            --query 'tasks[*].{TaskArn:taskArn,LastStatus:lastStatus,HealthStatus:healthStatus,CreatedAt:createdAt}' --output table
    else
        echo "No tasks running"
    fi
    
    # Get Load Balancer URL
    echo ""
    echo "🌐 Application URL:"
    LB_DNS=$($AWS_CMD cloudformation describe-stacks --stack-name RpaOcrEcsStack --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' --output text)
    echo "   http://$LB_DNS"
    
    # Test health endpoint
    echo ""
    echo "🏥 Health Check:"
    if curl -s -o /dev/null -w "%{http_code}" "http://$LB_DNS/health" | grep -q "200"; then
        echo "✅ Health check: PASSED"
    else
        echo "❌ Health check: FAILED"
    fi
    
else
    echo "❌ CloudFormation Stack: NOT FOUND"
    echo "Run './deploy.sh' to deploy the stack"
    if [ ! -z "$AWS_PROFILE" ]; then
        echo "Or run './deploy.sh -p $AWS_PROFILE' to use your profile"
    fi
fi

echo ""
echo "📊 Recent Logs (last 10 minutes):"
$AWS_CMD logs tail /ecs/rpa-ocr --since 10m --region $REGION 2>/dev/null || echo "No recent logs found"
