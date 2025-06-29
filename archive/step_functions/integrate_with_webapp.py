"""
Integration module to connect the web application with Step Functions RPA workflow
"""

import boto3
import json
import uuid
from datetime import datetime
from botocore.exceptions import ClientError

class StepFunctionRPAIntegration:
    def __init__(self, state_machine_arn, region='us-east-1', aws_profile=None):
        self.state_machine_arn = state_machine_arn
        
        # Create AWS session with profile support
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)
            
        self.stepfunctions_client = session.client('stepfunctions')
        self.s3_client = session.client('s3')
        
    def trigger_rpa_workflow(self, s3_bucket, s3_key, document_type='medical', session_id=None):
        """
        Trigger the Step Functions RPA workflow
        This replaces the direct Nova processing in the web app
        """
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Prepare input for Step Functions
        workflow_input = {
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "document_type": document_type,
            "session_id": session_id,
            "triggered_at": datetime.now().isoformat(),
            "trigger_source": "web_application"
        }
        
        try:
            # Start Step Functions execution
            response = self.stepfunctions_client.start_execution(
                stateMachineArn=self.state_machine_arn,
                name=f"medical-ocr-{session_id}",
                input=json.dumps(workflow_input)
            )
            
            return {
                'success': True,
                'execution_arn': response['executionArn'],
                'session_id': session_id,
                'workflow_input': workflow_input
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': str(e),
                'session_id': session_id
            }
    
    def check_workflow_status(self, execution_arn):
        """Check the status of a Step Functions execution"""
        try:
            response = self.stepfunctions_client.describe_execution(
                executionArn=execution_arn
            )
            
            return {
                'status': response['status'],
                'start_date': response['startDate'].isoformat(),
                'stop_date': response.get('stopDate', '').isoformat() if response.get('stopDate') else None,
                'input': json.loads(response['input']),
                'output': json.loads(response.get('output', '{}')) if response.get('output') else {}
            }
            
        except ClientError as e:
            return {
                'error': str(e)
            }
    
    def get_execution_history(self, execution_arn):
        """Get detailed execution history for debugging"""
        try:
            response = self.stepfunctions_client.get_execution_history(
                executionArn=execution_arn,
                maxResults=100,
                reverseOrder=True
            )
            
            return {
                'events': response['events']
            }
            
        except ClientError as e:
            return {
                'error': str(e)
            }

# Modified Flask routes to integrate with Step Functions
def create_step_function_routes(app, rpa_integration):
    """
    Add Step Functions integration routes to the Flask app
    """
    
    @app.route('/upload_rpa', methods=['POST'])
    def upload_document_rpa():
        """Upload document and trigger RPA workflow via Step Functions"""
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            try:
                # Generate session ID
                session_id = str(uuid.uuid4())
                
                # Upload file to S3
                s3_key = f"uploads/{datetime.now().strftime('%Y/%m/%d')}/{session_id}/{secure_filename(file.filename)}"
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=file.read(),
                    ContentType=file.content_type
                )
                
                # Trigger Step Functions RPA workflow
                workflow_result = rpa_integration.trigger_rpa_workflow(
                    s3_bucket=S3_BUCKET,
                    s3_key=s3_key,
                    document_type='medical',
                    session_id=session_id
                )
                
                if workflow_result['success']:
                    return jsonify({
                        'success': True,
                        'session_id': session_id,
                        'execution_arn': workflow_result['execution_arn'],
                        'message': 'Document uploaded and RPA workflow started',
                        'status_check_url': f'/status/{session_id}'
                    })
                else:
                    return jsonify({
                        'error': f'Failed to start RPA workflow: {workflow_result["error"]}'
                    }), 500
                    
            except Exception as e:
                return jsonify({'error': f'Processing failed: {str(e)}'}), 500
        
        return jsonify({'error': 'Invalid file type'}), 400
    
    @app.route('/status/<session_id>')
    def check_processing_status(session_id):
        """Check the status of document processing"""
        try:
            # In a real implementation, you'd store the execution ARN
            # For now, we'll construct it based on naming convention
            execution_name = f"medical-ocr-{session_id}"
            
            # List recent executions to find the one we want
            executions = stepfunctions_client.list_executions(
                stateMachineArn=rpa_integration.state_machine_arn,
                maxResults=50
            )
            
            target_execution = None
            for execution in executions['executions']:
                if execution['name'] == execution_name:
                    target_execution = execution
                    break
            
            if not target_execution:
                return jsonify({'error': 'Execution not found'}), 404
            
            status_info = rpa_integration.check_workflow_status(target_execution['executionArn'])
            
            return jsonify({
                'session_id': session_id,
                'status': status_info['status'],
                'details': status_info
            })
            
        except Exception as e:
            return jsonify({'error': f'Status check failed: {str(e)}'}), 500
    
    @app.route('/results/<session_id>')
    def get_processing_results(session_id):
        """Get the final results of document processing"""
        try:
            # Check if results are available in S3
            results_key = f"processed/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
            
            try:
                response = s3_client.get_object(Bucket=S3_BUCKET, Key=results_key)
                results = json.loads(response['Body'].read())
                
                return jsonify({
                    'session_id': session_id,
                    'results': results,
                    'status': 'completed'
                })
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    return jsonify({
                        'session_id': session_id,
                        'status': 'processing',
                        'message': 'Results not yet available'
                    })
                else:
                    raise e
                    
        except Exception as e:
            return jsonify({'error': f'Failed to get results: {str(e)}'}), 500

# Example usage in your main app.py
def integrate_step_functions_with_webapp():
    """
    Example of how to integrate Step Functions with your existing web app
    """
    
    # Initialize Step Functions integration
    STATE_MACHINE_ARN = os.getenv('STEP_FUNCTION_ARN', 'arn:aws:states:us-east-1:123456789012:stateMachine:MedicalOCRProcessingWorkflow')
    rpa_integration = StepFunctionRPAIntegration(STATE_MACHINE_ARN)
    
    # Add the new routes to your Flask app
    # create_step_function_routes(app, rpa_integration)
    
    return rpa_integration

# Webhook handler for Step Functions notifications
def handle_step_function_webhook(event, context):
    """
    Lambda function to handle Step Functions completion notifications
    This can update your web application when processing is complete
    """
    
    try:
        # Parse the SNS message
        if 'Records' in event:
            for record in event['Records']:
                if record['EventSource'] == 'aws:sns':
                    message = json.loads(record['Sns']['Message'])
                    
                    session_id = message.get('session_id')
                    status = message.get('status')
                    
                    if status == 'completed':
                        # Notify web application that processing is complete
                        # You could use WebSockets, database updates, etc.
                        print(f"Processing completed for session {session_id}")
                        
                        # Example: Update database status
                        # update_processing_status(session_id, 'completed')
                        
                    elif status == 'failed':
                        print(f"Processing failed for session {session_id}")
                        # Handle failure case
        
        return {
            'statusCode': 200,
            'body': json.dumps('Webhook processed successfully')
        }
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
