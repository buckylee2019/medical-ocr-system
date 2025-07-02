# RPA OCR ECS Fargate Deployment

This CDK stack deploys your RPA OCR Flask web application to AWS ECS using Fargate.

## Architecture

- **ECS Fargate**: Serverless container hosting
- **Application Load Balancer**: HTTP traffic distribution
- **VPC**: Isolated network with public/private subnets
- **Auto Scaling**: CPU and memory-based scaling
- **CloudWatch Logs**: Centralized logging
- **IAM Roles**: Secure access to AWS services

## Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Python 3.8+** installed
3. **Docker** installed and running
4. **Node.js** (for CDK CLI)

## Quick Start

1. **Install CDK CLI** (if not already installed):
   ```bash
   npm install -g aws-cdk
   ```

2. **Deploy the stack**:
   ```bash
   # Using default AWS profile
   ./deploy.sh
   
   # Using specific AWS profile
   ./deploy.sh -p my-profile
   
   # Using specific profile and region
   ./deploy.sh -p my-profile -r us-east-1
   ```

3. **Check deployment status**:
   ```bash
   # Using default profile
   ./status.sh
   
   # Using specific profile
   ./status.sh -p my-profile
   ```

4. **Access your application**:
   - The script will output the Load Balancer DNS name
   - Wait 2-3 minutes for the service to become healthy
   - Access via: `http://<load-balancer-dns>`

## Manual Deployment Steps

If you prefer manual deployment:

1. **Set up environment**:
   ```bash
   # For default profile
   export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
   export CDK_DEFAULT_REGION=$(aws configure get region)
   
   # For specific profile
   export AWS_PROFILE=my-profile
   export CDK_DEFAULT_ACCOUNT=$(aws --profile my-profile sts get-caller-identity --query Account --output text)
   export CDK_DEFAULT_REGION=$(aws --profile my-profile configure get region)
   ```

2. **Install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Bootstrap CDK** (first time only):
   ```bash
   # Default profile
   cdk bootstrap
   
   # Specific profile
   cdk bootstrap --profile my-profile
   ```

4. **Deploy**:
   ```bash
   # Default profile
   cdk deploy
   
   # Specific profile
   cdk deploy --profile my-profile
   ```

## Configuration

### Environment Variables

The following environment variables are set in the container:

- `AWS_REGION`: us-west-2
- `S3_BUCKET`: medical-ocr-documents
- `DYNAMODB_TABLE_NAME`: medical-ocr-results
- `DYNAMODB_IMAGES_TABLE_NAME`: medical-ocr-images
- `FLASK_ENV`: production

### Resource Configuration

- **CPU**: 1024 (1 vCPU)
- **Memory**: 2048 MB (2 GB)
- **Auto Scaling**: 1-10 tasks
- **Health Check**: `/health` endpoint
- **Log Retention**: 1 week

## Monitoring

### CloudWatch Logs
```bash
aws logs tail /ecs/rpa-ocr --follow
```

### Service Status
```bash
aws ecs describe-services --cluster rpa-ocr-cluster --services rpa-ocr-service
```

### Task Status
```bash
aws ecs list-tasks --cluster rpa-ocr-cluster --service-name rpa-ocr-service
```

## Scaling

The service automatically scales based on:
- **CPU utilization**: Target 70%
- **Memory utilization**: Target 80%
- **Scale out cooldown**: 5 minutes
- **Scale in cooldown**: 5 minutes

## Security

### IAM Permissions

The ECS task has the following AWS permissions:
- **Amazon Bedrock**: Full access for AI model inference
- **Amazon S3**: Full access for document storage
- **Amazon DynamoDB**: Full access for data persistence

### Network Security

- Tasks run in private subnets
- Only the Load Balancer is publicly accessible
- Security groups restrict traffic to necessary ports

## Troubleshooting

### Common Issues

1. **Service not starting**:
   ```bash
   aws ecs describe-services --cluster rpa-ocr-cluster --services rpa-ocr-service
   ```

2. **Health check failures**:
   ```bash
   aws logs tail /ecs/rpa-ocr --follow
   ```

3. **Image build issues**:
   - Ensure Docker is running
   - Check Dockerfile syntax
   - Verify all dependencies in requirements.txt

### Useful Commands

```bash
# View stack outputs
aws cloudformation describe-stacks --stack-name RpaOcrEcsStack --query 'Stacks[0].Outputs'

# Force new deployment
aws ecs update-service --cluster rpa-ocr-cluster --service rpa-ocr-service --force-new-deployment

# Scale service manually
aws ecs update-service --cluster rpa-ocr-cluster --service rpa-ocr-service --desired-count 2
```

## Cleanup

To remove all resources:

```bash
# Using default profile
./cleanup.sh

# Using specific profile
./cleanup.sh -p my-profile

# Using specific profile and region
./cleanup.sh -p my-profile -r us-east-1
```

Or manually:

```bash
# Default profile
cdk destroy

# Specific profile
cdk destroy --profile my-profile
```

## Cost Optimization

- **Fargate Spot**: Consider using Spot instances for non-production
- **Reserved Capacity**: For predictable workloads
- **Right-sizing**: Monitor CPU/memory usage and adjust
- **Log Retention**: Adjust CloudWatch log retention period

## Next Steps

1. **Custom Domain**: Add Route 53 and SSL certificate
2. **HTTPS**: Configure ALB with SSL/TLS
3. **CI/CD**: Set up automated deployments
4. **Monitoring**: Add CloudWatch alarms and dashboards
5. **Backup**: Configure automated backups for DynamoDB
