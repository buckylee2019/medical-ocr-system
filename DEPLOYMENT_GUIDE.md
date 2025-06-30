# 🚀 AWS Deployment Guide - Medical OCR System

## 📋 Overview

This guide provides multiple options for deploying the Medical OCR System to AWS. The system is already designed to work with AWS services (DynamoDB, S3, Bedrock), making cloud deployment straightforward.

## 🎯 Deployment Options

### 1. AWS App Runner (Recommended - Easiest)
**Best for**: Quick deployment, automatic scaling, minimal configuration

**Pros**:
- ✅ Fully managed service
- ✅ Automatic scaling
- ✅ Built-in load balancing
- ✅ Easy CI/CD integration
- ✅ Pay-per-use pricing

**Cons**:
- ❌ Less control over infrastructure
- ❌ Limited customization options

### 2. AWS Elastic Beanstalk
**Best for**: Traditional web applications, more control than App Runner

**Pros**:
- ✅ Easy deployment and management
- ✅ Auto-scaling and load balancing
- ✅ Health monitoring
- ✅ Multiple environment support

**Cons**:
- ❌ More complex than App Runner
- ❌ EC2 costs even when idle

### 3. AWS ECS Fargate
**Best for**: Containerized applications, production workloads

**Pros**:
- ✅ Full container control
- ✅ Serverless containers
- ✅ Integration with AWS services
- ✅ High availability

**Cons**:
- ❌ More complex setup
- ❌ Requires container knowledge

### 4. AWS Lambda + API Gateway (Serverless)
**Best for**: Cost optimization, sporadic usage

**Pros**:
- ✅ Pay-per-request pricing
- ✅ Automatic scaling
- ✅ No server management

**Cons**:
- ❌ Cold start latency
- ❌ 15-minute timeout limit
- ❌ Complex for file uploads

## 🚀 Quick Start - App Runner Deployment

### Prerequisites
```bash
# 1. AWS CLI configured
aws configure

# 2. Required permissions
# - DynamoDB full access
# - S3 full access
# - Bedrock full access
# - App Runner full access
# - IAM role creation

# 3. Python environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install boto3
```

### Step 1: Prepare Your Code
```bash
# 1. Clone/prepare your repository
git clone <your-repo-url>
cd medical-ocr

# 2. Update environment variables
cp .env.example .env
# Edit .env with production values

# 3. Test locally first
python app.py
```

### Step 2: Run Deployment Script
```bash
cd deploy
python deploy.py
```

### Step 3: Manual Configuration
1. **GitHub Repository**: Connect your GitHub repo to App Runner
2. **Environment Variables**: Set in App Runner console
3. **Domain**: Configure custom domain (optional)

## 🔧 Detailed Deployment Instructions

### Option 1: AWS App Runner

#### 1. Create apprunner.yaml
```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install -r requirements.txt
run:
  runtime-version: 3.11
  command: python app.py
  network:
    port: 5006
  env:
    - name: AWS_DEFAULT_REGION
      value: us-west-2
    - name: DYNAMODB_TABLE_NAME
      value: medical-ocr-data
    - name: S3_BUCKET
      value: your-medical-ocr-bucket
```

#### 2. Deploy via AWS Console
1. Go to AWS App Runner console
2. Create service
3. Connect GitHub repository
4. Configure build settings
5. Set environment variables
6. Deploy

### Option 2: Docker + ECS Fargate

#### 1. Build Docker Image
```bash
# Build image
docker build -t medical-ocr .

# Test locally
docker run -p 5006:5006 medical-ocr
```

#### 2. Push to ECR
```bash
# Create ECR repository
aws ecr create-repository --repository-name medical-ocr

# Get login token
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-west-2.amazonaws.com

# Tag and push
docker tag medical-ocr:latest <account-id>.dkr.ecr.us-west-2.amazonaws.com/medical-ocr:latest
docker push <account-id>.dkr.ecr.us-west-2.amazonaws.com/medical-ocr:latest
```

#### 3. Create ECS Service
```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create ECS cluster
aws ecs create-cluster --cluster-name medical-ocr-cluster

# Create service
aws ecs create-service --cluster medical-ocr-cluster --service-name medical-ocr-service --task-definition medical-ocr-app --desired-count 1
```

## 🔐 Security Configuration

### IAM Roles and Policies
```json
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
      "Resource": "arn:aws:dynamodb:*:*:table/medical-ocr-data"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GeneratePresignedUrl"
      ],
      "Resource": "arn:aws:s3:::your-medical-ocr-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    }
  ]
}
```

### Environment Variables
```bash
# Production environment variables
AWS_DEFAULT_REGION=us-west-2
DYNAMODB_TABLE_NAME=medical-ocr-data
S3_BUCKET=your-medical-ocr-bucket
FLASK_ENV=production
FLASK_DEBUG=False
```

## 📊 Monitoring and Logging

### CloudWatch Setup
```bash
# Create log group
aws logs create-log-group --log-group-name /aws/apprunner/medical-ocr

# Set up alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "medical-ocr-high-error-rate" \
  --alarm-description "High error rate in medical OCR app" \
  --metric-name ErrorRate \
  --namespace AWS/AppRunner \
  --statistic Average \
  --period 300 \
  --threshold 5.0 \
  --comparison-operator GreaterThanThreshold
```

### Health Check Endpoint
Add to your `app.py`:
```python
@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    try:
        # Test DynamoDB connection
        dynamodb_table.scan(Limit=1)
        
        # Test S3 connection
        s3_client.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=1)
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'dynamodb': 'ok',
                's3': 'ok',
                'bedrock': 'ok'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
```

## 💰 Cost Optimization

### App Runner Pricing (Estimated)
- **Provisioned**: ~$25/month for 1 vCPU, 2GB RAM
- **Request-based**: $0.064 per vCPU hour + $0.007 per GB hour
- **Data transfer**: $0.09 per GB

### Cost Optimization Tips
1. **Use appropriate instance sizes**
2. **Enable auto-scaling**
3. **Monitor usage patterns**
4. **Use S3 lifecycle policies**
5. **Optimize DynamoDB read/write capacity**

## 🔧 Troubleshooting

### Common Issues

#### 1. Bedrock Access Denied
```bash
# Enable Bedrock model access
aws bedrock put-model-invocation-logging-configuration \
  --logging-config cloudWatchConfig='{logGroupName="/aws/bedrock/modelinvocations",roleArn="arn:aws:iam::ACCOUNT:role/service-role/AmazonBedrockExecutionRoleForCloudWatchLogs"}'
```

#### 2. DynamoDB Connection Issues
- Check IAM permissions
- Verify table name and region
- Test with AWS CLI: `aws dynamodb describe-table --table-name medical-ocr-data`

#### 3. S3 Upload Failures
- Check bucket permissions
- Verify CORS configuration
- Test with AWS CLI: `aws s3 ls s3://your-bucket-name`

### Debug Commands
```bash
# Check App Runner service status
aws apprunner describe-service --service-arn <service-arn>

# View logs
aws logs tail /aws/apprunner/medical-ocr --follow

# Test endpoints
curl https://your-app-url.us-west-2.awsapprunner.com/health
```

## 📋 Deployment Checklist

### Pre-deployment
- [ ] AWS credentials configured
- [ ] Required IAM permissions
- [ ] Environment variables set
- [ ] Code tested locally
- [ ] Dependencies updated

### Deployment
- [ ] S3 bucket created
- [ ] DynamoDB table created
- [ ] IAM roles configured
- [ ] Application deployed
- [ ] Health check passing

### Post-deployment
- [ ] Custom domain configured (optional)
- [ ] SSL certificate installed
- [ ] Monitoring set up
- [ ] Backup strategy implemented
- [ ] Security review completed

## 🎯 Next Steps

1. **Choose deployment method** based on your needs
2. **Run the deployment script** or follow manual steps
3. **Configure monitoring** and alerting
4. **Set up CI/CD pipeline** for automated deployments
5. **Implement backup strategy** for data protection
6. **Performance testing** under expected load

---

**Need Help?** 
- Check AWS documentation for specific services
- Use AWS Support for technical issues
- Monitor CloudWatch logs for debugging
- Test thoroughly before production use
