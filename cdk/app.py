#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.rpa_ocr_ecs_stack import RpaOcrEcsStack

app = cdk.App()

# Get environment variables
account = os.environ.get('CDK_DEFAULT_ACCOUNT')
region = os.environ.get('CDK_DEFAULT_REGION', 'us-west-2')

RpaOcrEcsStack(
    app, 
    "RpaOcrEcsStack",
    env=cdk.Environment(account=account, region=region),
    description="RPA OCR Web Application on ECS Fargate"
)

app.synth()
