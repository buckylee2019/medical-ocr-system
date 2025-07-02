# RPA OCR ECS Fargate Deployment

## 🎯 Overview

Your Flask web application has been configured for deployment to AWS ECS using Fargate. This setup provides a scalable, serverless container platform that automatically manages infrastructure.

## 📁 Files Created

### CDK Infrastructure
- `cdk/app.py` - CDK application entry point
- `cdk/stacks/rpa_ocr_ecs_stack.py` - Main ECS Fargate stack
- `cdk/requirements.txt` - CDK dependencies
- `cdk/cdk.json` - CDK configuration

### Docker Configuration
- `Dockerfile` - Container image definition
- `.dockerignore` - Files to exclude from Docker build

### Deployment Scripts
- `cdk/deploy.sh` - Automated deployment script
- `cdk/cleanup.sh` - Resource cleanup script
- `cdk/status.sh` - Service status checker

## 🏗️ Architecture

```
Internet → ALB → ECS Fargate Tasks (Private Subnets)
                      ↓
              AWS Services (Bedrock, S3, DynamoDB)
```

### Key Components:
- **VPC**: Isolated network with public/private subnets
- **Application Load Balancer**: Distributes HTTP traffic
- **ECS Fargate**: Serverless container hosting
- **Auto Scaling**: Scales 1-10 tasks based on CPU/memory
- **CloudWatch**: Centralized logging and monitoring

## 🚀 Quick Deployment

1. **Navigate to CDK directory**:
   ```bash
   cd cdk
   ```

2. **Run deployment**:
   ```bash
   # Using default AWS profile
   ./deploy.sh
   
   # Using specific AWS profile
   ./deploy.sh -p my-aws-profile
   
   # Using specific profile and region
   ./deploy.sh -p my-aws-profile -r us-east-1
   ```

3. **Check status**:
   ```bash
   # Using default profile
   ./status.sh
   
   # Using specific profile
   ./status.sh -p my-aws-profile
   ```

### Script Options:

All scripts (`deploy.sh`, `cleanup.sh`, `status.sh`) support:
- `-p, --profile PROFILE` - AWS profile to use
- `-r, --region REGION` - AWS region to deploy to
- `-h, --help` - Show help message

## 🔧 Configuration

### Container Specs:
- **CPU**: 1024 (1 vCPU)
- **Memory**: 2048 MB
- **Port**: 5000
- **Health Check**: `/health` endpoint

### Environment Variables:
- `AWS_REGION`: us-west-2
- `S3_BUCKET`: medical-ocr-documents
- `DYNAMODB_TABLE_NAME`: medical-ocr-results
- `DYNAMODB_IMAGES_TABLE_NAME`: medical-ocr-images
- `FLASK_ENV`: production

### Auto Scaling:
- **Min Tasks**: 1
- **Max Tasks**: 10
- **CPU Target**: 70%
- **Memory Target**: 80%

## 🔐 Security

### IAM Permissions:
- Amazon Bedrock Full Access
- Amazon S3 Full Access
- Amazon DynamoDB Full Access

### Network Security:
- Tasks in private subnets
- ALB in public subnets
- Security groups restrict access

## 📊 Monitoring

### CloudWatch Logs:
```bash
aws logs tail /ecs/rpa-ocr --follow
```

### Service Status:
```bash
aws ecs describe-services --cluster rpa-ocr-cluster --services rpa-ocr-service
```

## 💰 Cost Estimation

**Monthly costs (approximate)**:
- **Fargate**: ~$30-50/month (1 task running 24/7)
- **ALB**: ~$20/month
- **NAT Gateway**: ~$45/month
- **CloudWatch Logs**: ~$5/month

**Total**: ~$100-120/month for basic usage

## 🛠️ Troubleshooting

### Common Issues:

1. **Deployment fails**:
   - Check AWS credentials: `aws sts get-caller-identity`
   - Verify Docker is running
   - Check CDK bootstrap: `cdk bootstrap`

2. **Service unhealthy**:
   - Check logs: `aws logs tail /ecs/rpa-ocr --follow`
   - Verify health endpoint: `curl http://<alb-dns>/health`

3. **Can't access application**:
   - Wait 2-3 minutes after deployment
   - Check security groups
   - Verify ALB target group health

### Useful Commands:

```bash
# Force new deployment
aws ecs update-service --cluster rpa-ocr-cluster --service rpa-ocr-service --force-new-deployment

# Scale manually
aws ecs update-service --cluster rpa-ocr-cluster --service rpa-ocr-service --desired-count 2

# View stack outputs
aws cloudformation describe-stacks --stack-name RpaOcrEcsStack --query 'Stacks[0].Outputs'
```

## 🔄 Next Steps

1. **Custom Domain**: Add Route 53 and SSL certificate
2. **HTTPS**: Configure ALB with SSL/TLS
3. **CI/CD**: Set up automated deployments with CodePipeline
4. **Monitoring**: Add CloudWatch alarms and dashboards
5. **Backup**: Configure DynamoDB backups

## 🧹 Cleanup

To remove all resources:
```bash
cd cdk

# Using default profile
./cleanup.sh

# Using specific profile
./cleanup.sh -p my-aws-profile
```

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review CloudWatch logs
3. Verify AWS permissions
4. Ensure all prerequisites are met

---

**Ready to deploy?** Run `cd cdk && ./deploy.sh` to get started! 🚀
