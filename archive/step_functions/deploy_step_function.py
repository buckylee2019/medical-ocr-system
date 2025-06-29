#!/usr/bin/env python3
"""
Deploy Step Functions workflow for Medical OCR RPA automation
"""

import boto3
import json
import os
from botocore.exceptions import ClientError

def create_step_function_role():
    """Create IAM role for Step Functions"""
    iam_client = boto3.client('iam')
    
    # Trust policy for Step Functions
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "states.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # Permissions policy
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": "arn:aws:lambda:*:*:function:medical-ocr-*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:SendMessage"
                ],
                "Resource": "arn:aws:sqs:*:*:medical-ocr-*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sns:Publish"
                ],
                "Resource": "arn:aws:sns:*:*:medical-ocr-*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem"
                ],
                "Resource": "arn:aws:dynamodb:*:*:table/medical-ocr-*"
            }
        ]
    }
    
    try:
        # Create role
        role_response = iam_client.create_role(
            RoleName='MedicalOCRStepFunctionRole',
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for Medical OCR Step Functions workflow'
        )
        
        # Attach permissions policy
        iam_client.put_role_policy(
            RoleName='MedicalOCRStepFunctionRole',
            PolicyName='MedicalOCRStepFunctionPolicy',
            PolicyDocument=json.dumps(permissions_policy)
        )
        
        print("✅ Created Step Functions IAM role")
        return role_response['Role']['Arn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            # Role already exists, get its ARN
            role_response = iam_client.get_role(RoleName='MedicalOCRStepFunctionRole')
            print("✅ Step Functions IAM role already exists")
            return role_response['Role']['Arn']
        else:
            print(f"❌ Error creating IAM role: {e}")
            return None

def create_sqs_queues():
    """Create SQS queues for human review and manual processing"""
    sqs_client = boto3.client('sqs')
    
    queues = [
        'medical-ocr-human-review-queue',
        'medical-ocr-manual-processing-queue'
    ]
    
    queue_urls = {}
    
    for queue_name in queues:
        try:
            response = sqs_client.create_queue(
                QueueName=queue_name,
                Attributes={
                    'VisibilityTimeoutSeconds': '300',
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'ReceiveMessageWaitTimeSeconds': '20'  # Long polling
                }
            )
            queue_urls[queue_name] = response['QueueUrl']
            print(f"✅ Created SQS queue: {queue_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'QueueAlreadyExists':
                # Get existing queue URL
                response = sqs_client.get_queue_url(QueueName=queue_name)
                queue_urls[queue_name] = response['QueueUrl']
                print(f"✅ SQS queue already exists: {queue_name}")
            else:
                print(f"❌ Error creating SQS queue {queue_name}: {e}")
    
    return queue_urls

def create_sns_topics():
    """Create SNS topics for notifications"""
    sns_client = boto3.client('sns')
    
    topics = [
        'medical-ocr-alerts',
        'medical-ocr-completion',
        'medical-ocr-errors'
    ]
    
    topic_arns = {}
    
    for topic_name in topics:
        try:
            response = sns_client.create_topic(Name=topic_name)
            topic_arns[topic_name] = response['TopicArn']
            print(f"✅ Created SNS topic: {topic_name}")
            
        except ClientError as e:
            print(f"❌ Error creating SNS topic {topic_name}: {e}")
    
    return topic_arns

def create_dynamodb_table():
    """Create DynamoDB table for processing logs"""
    dynamodb_client = boto3.client('dynamodb')
    
    try:
        response = dynamodb_client.create_table(
            TableName='medical-ocr-processing-log',
            KeySchema=[
                {
                    'AttributeName': 'session_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'session_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        print("✅ Created DynamoDB table: medical-ocr-processing-log")
        return response['TableDescription']['TableArn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            # Table already exists
            response = dynamodb_client.describe_table(TableName='medical-ocr-processing-log')
            print("✅ DynamoDB table already exists: medical-ocr-processing-log")
            return response['Table']['TableArn']
        else:
            print(f"❌ Error creating DynamoDB table: {e}")
            return None

def deploy_step_function(role_arn):
    """Deploy the Step Functions state machine"""
    stepfunctions_client = boto3.client('stepfunctions')
    
    # Load the state machine definition
    with open('document_processing_workflow.json', 'r') as f:
        definition = f.read()
    
    try:
        response = stepfunctions_client.create_state_machine(
            name='MedicalOCRProcessingWorkflow',
            definition=definition,
            roleArn=role_arn,
            type='STANDARD',
            loggingConfiguration={
                'level': 'ERROR',
                'includeExecutionData': False,
                'destinations': [
                    {
                        'cloudWatchLogsLogGroup': {
                            'logGroupArn': f'arn:aws:logs:{boto3.Session().region_name}:*:log-group:/aws/stepfunctions/MedicalOCRProcessingWorkflow'
                        }
                    }
                ]
            }
        )
        
        print("✅ Created Step Functions state machine: MedicalOCRProcessingWorkflow")
        return response['stateMachineArn']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'StateMachineAlreadyExists':
            # Update existing state machine
            try:
                # Get existing state machine ARN
                list_response = stepfunctions_client.list_state_machines()
                state_machine_arn = None
                for sm in list_response['stateMachines']:
                    if sm['name'] == 'MedicalOCRProcessingWorkflow':
                        state_machine_arn = sm['stateMachineArn']
                        break
                
                if state_machine_arn:
                    stepfunctions_client.update_state_machine(
                        stateMachineArn=state_machine_arn,
                        definition=definition,
                        roleArn=role_arn
                    )
                    print("✅ Updated existing Step Functions state machine")
                    return state_machine_arn
                    
            except ClientError as update_error:
                print(f"❌ Error updating state machine: {update_error}")
        else:
            print(f"❌ Error creating state machine: {e}")
    
    return None

def create_lambda_functions():
    """Create placeholder Lambda functions (you'll need to implement these)"""
    lambda_client = boto3.client('lambda')
    
    functions = [
        'medical-ocr-validate-input',
        'medical-ocr-preprocess',
        'medical-ocr-nova-processor',
        'medical-ocr-data-validator',
        'medical-ocr-auto-approve',
        'medical-ocr-check-review-status',
        'medical-ocr-save-to-s3',
        'medical-ocr-error-handler'
    ]
    
    # Basic Lambda function code
    basic_code = '''
def lambda_handler(event, context):
    print(f"Function called with event: {event}")
    return {
        'statusCode': 200,
        'body': 'Function placeholder - implement actual logic'
    }
'''
    
    for func_name in functions:
        try:
            # Create a simple placeholder function
            lambda_client.create_function(
                FunctionName=func_name,
                Runtime='python3.9',
                Role=f'arn:aws:iam::{boto3.client("sts").get_caller_identity()["Account"]}:role/lambda-execution-role',
                Handler='index.lambda_handler',
                Code={'ZipFile': basic_code.encode()},
                Description=f'Medical OCR processing function: {func_name}',
                Timeout=300,
                MemorySize=512
            )
            print(f"✅ Created Lambda function: {func_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceConflictException':
                print(f"✅ Lambda function already exists: {func_name}")
            else:
                print(f"❌ Error creating Lambda function {func_name}: {e}")

def main():
    """Main deployment function"""
    print("🚀 Deploying Medical OCR Step Functions RPA Workflow")
    print("=" * 60)
    
    # Create IAM role
    role_arn = create_step_function_role()
    if not role_arn:
        print("❌ Failed to create IAM role. Exiting.")
        return
    
    # Create supporting resources
    queue_urls = create_sqs_queues()
    topic_arns = create_sns_topics()
    table_arn = create_dynamodb_table()
    
    # Create Lambda functions (placeholders)
    print("\n📝 Note: Creating placeholder Lambda functions.")
    print("   You'll need to implement the actual logic in each function.")
    create_lambda_functions()
    
    # Deploy Step Functions
    state_machine_arn = deploy_step_function(role_arn)
    
    if state_machine_arn:
        print("\n" + "=" * 60)
        print("✅ Deployment Complete!")
        print(f"📊 State Machine ARN: {state_machine_arn}")
        print(f"🔐 IAM Role ARN: {role_arn}")
        print("\n📋 Next Steps:")
        print("1. Implement the Lambda functions with actual logic")
        print("2. Update your web application to trigger the Step Function")
        print("3. Configure SNS topic subscriptions for notifications")
        print("4. Test the workflow with sample documents")
        print("\n🔧 To trigger the workflow:")
        print("aws stepfunctions start-execution \\")
        print(f"  --state-machine-arn {state_machine_arn} \\")
        print('  --input \'{"s3_bucket":"your-bucket","s3_key":"path/to/document","session_id":"test-123"}\'')
    else:
        print("❌ Failed to deploy Step Functions workflow")

if __name__ == "__main__":
    main()
