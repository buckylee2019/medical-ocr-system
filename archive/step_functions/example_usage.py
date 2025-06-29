#!/usr/bin/env python3
"""
Example usage of Step Functions RPA workflow for medical document processing
"""

import boto3
import json
import time
from datetime import datetime
from integrate_with_webapp import StepFunctionRPAIntegration

def example_document_processing():
    """
    Complete example of processing a medical document through the RPA workflow
    """
    
    # Initialize the RPA integration
    STATE_MACHINE_ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:MedicalOCRProcessingWorkflow"
    rpa = StepFunctionRPAIntegration(STATE_MACHINE_ARN)
    
    print("🏥 Medical Document RPA Processing Example")
    print("=" * 50)
    
    # Example 1: High-confidence document (auto-approved)
    print("\n📄 Example 1: High-Quality Prescription")
    result1 = rpa.trigger_rpa_workflow(
        s3_bucket="medical-ocr-documents",
        s3_key="samples/prescription_clear.pdf",
        document_type="prescription",
        session_id="example-001"
    )
    
    if result1['success']:
        print(f"✅ Workflow started: {result1['execution_arn']}")
        monitor_execution(rpa, result1['execution_arn'], "High-quality prescription")
    else:
        print(f"❌ Failed to start workflow: {result1['error']}")
    
    # Example 2: Medium-confidence document (human review)
    print("\n📄 Example 2: Handwritten Notes (Human Review Required)")
    result2 = rpa.trigger_rpa_workflow(
        s3_bucket="medical-ocr-documents",
        s3_key="samples/handwritten_notes.jpg",
        document_type="clinical_notes",
        session_id="example-002"
    )
    
    if result2['success']:
        print(f"✅ Workflow started: {result2['execution_arn']}")
        monitor_execution(rpa, result2['execution_arn'], "Handwritten clinical notes")
    else:
        print(f"❌ Failed to start workflow: {result2['error']}")
    
    # Example 3: Low-confidence document (manual processing)
    print("\n📄 Example 3: Poor Quality Scan (Manual Processing)")
    result3 = rpa.trigger_rpa_workflow(
        s3_bucket="medical-ocr-documents",
        s3_key="samples/poor_quality_scan.tiff",
        document_type="lab_report",
        session_id="example-003"
    )
    
    if result3['success']:
        print(f"✅ Workflow started: {result3['execution_arn']}")
        monitor_execution(rpa, result3['execution_arn'], "Poor quality lab report")
    else:
        print(f"❌ Failed to start workflow: {result3['error']}")

def monitor_execution(rpa, execution_arn, description):
    """Monitor a Step Functions execution until completion"""
    
    print(f"🔍 Monitoring: {description}")
    
    max_wait_time = 300  # 5 minutes
    check_interval = 10  # 10 seconds
    elapsed_time = 0
    
    while elapsed_time < max_wait_time:
        status_info = rpa.check_workflow_status(execution_arn)
        
        if 'error' in status_info:
            print(f"❌ Error checking status: {status_info['error']}")
            break
        
        status = status_info['status']
        print(f"   Status: {status} (elapsed: {elapsed_time}s)")
        
        if status == 'SUCCEEDED':
            print(f"✅ Workflow completed successfully!")
            print(f"   Output: {json.dumps(status_info['output'], indent=2)}")
            break
        elif status == 'FAILED':
            print(f"❌ Workflow failed!")
            print(f"   Details: {status_info}")
            break
        elif status == 'TIMED_OUT':
            print(f"⏰ Workflow timed out!")
            break
        elif status == 'ABORTED':
            print(f"🛑 Workflow was aborted!")
            break
        
        time.sleep(check_interval)
        elapsed_time += check_interval
    
    if elapsed_time >= max_wait_time:
        print(f"⏰ Monitoring timeout reached. Workflow may still be running.")

def batch_processing_example():
    """
    Example of processing multiple documents in batch
    """
    
    print("\n📚 Batch Processing Example")
    print("=" * 30)
    
    STATE_MACHINE_ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:MedicalOCRProcessingWorkflow"
    rpa = StepFunctionRPAIntegration(STATE_MACHINE_ARN)
    
    # List of documents to process
    documents = [
        {"key": "batch/prescription_001.pdf", "type": "prescription"},
        {"key": "batch/prescription_002.pdf", "type": "prescription"},
        {"key": "batch/lab_report_001.pdf", "type": "lab_report"},
        {"key": "batch/clinical_notes_001.jpg", "type": "clinical_notes"},
        {"key": "batch/discharge_summary_001.pdf", "type": "discharge_summary"}
    ]
    
    executions = []
    
    # Start all workflows
    for i, doc in enumerate(documents):
        session_id = f"batch-{datetime.now().strftime('%Y%m%d')}-{i+1:03d}"
        
        result = rpa.trigger_rpa_workflow(
            s3_bucket="medical-ocr-documents",
            s3_key=doc["key"],
            document_type=doc["type"],
            session_id=session_id
        )
        
        if result['success']:
            executions.append({
                'execution_arn': result['execution_arn'],
                'session_id': session_id,
                'document': doc["key"],
                'type': doc["type"]
            })
            print(f"✅ Started processing: {doc['key']}")
        else:
            print(f"❌ Failed to start: {doc['key']} - {result['error']}")
    
    # Monitor all executions
    print(f"\n🔍 Monitoring {len(executions)} batch executions...")
    
    completed = 0
    max_wait = 600  # 10 minutes
    start_time = time.time()
    
    while completed < len(executions) and (time.time() - start_time) < max_wait:
        for execution in executions:
            if execution.get('completed'):
                continue
                
            status_info = rpa.check_workflow_status(execution['execution_arn'])
            
            if status_info.get('status') in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
                execution['completed'] = True
                execution['final_status'] = status_info.get('status')
                completed += 1
                
                print(f"   {execution['document']}: {execution['final_status']}")
        
        if completed < len(executions):
            time.sleep(15)  # Check every 15 seconds
    
    # Summary
    print(f"\n📊 Batch Processing Summary:")
    print(f"   Total documents: {len(documents)}")
    print(f"   Successfully started: {len(executions)}")
    print(f"   Completed: {completed}")
    
    # Status breakdown
    status_counts = {}
    for execution in executions:
        if execution.get('completed'):
            status = execution['final_status']
            status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in status_counts.items():
        print(f"   {status}: {count}")

def human_review_simulation():
    """
    Simulate the human review process
    """
    
    print("\n👤 Human Review Simulation")
    print("=" * 30)
    
    # This would typically be a separate service/application
    # that monitors the human review queue and processes items
    
    sqs_client = boto3.client('sqs')
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/medical-ocr-human-review-queue"
    
    try:
        # Check for messages in the human review queue
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10
        )
        
        messages = response.get('Messages', [])
        
        if not messages:
            print("📭 No documents in human review queue")
            return
        
        print(f"📬 Found {len(messages)} documents for review")
        
        for message in messages:
            body = json.loads(message['Body'])
            session_id = body.get('session_id')
            confidence_score = body.get('confidence_score')
            
            print(f"\n📄 Reviewing document: {session_id}")
            print(f"   Confidence Score: {confidence_score:.2f}")
            print(f"   Extracted Data: {json.dumps(body.get('extracted_data', {}), indent=4)}")
            
            # Simulate human review decision
            # In a real application, this would be done through a web interface
            review_decision = simulate_human_decision(confidence_score)
            
            print(f"   👤 Human Decision: {review_decision}")
            
            # In a real implementation, you would:
            # 1. Update the document status in your database
            # 2. Trigger the Step Functions workflow to continue
            # 3. Delete the message from the queue
            
            # For simulation, just delete the message
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
    
    except Exception as e:
        print(f"❌ Error accessing review queue: {str(e)}")

def simulate_human_decision(confidence_score):
    """Simulate human review decision based on confidence score"""
    
    if confidence_score > 0.7:
        return "APPROVED - Minor corrections made"
    elif confidence_score > 0.4:
        return "APPROVED - Significant corrections made"
    else:
        return "REJECTED - Requires manual re-entry"

def cost_analysis_example():
    """
    Example cost analysis for Step Functions RPA vs traditional RPA
    """
    
    print("\n💰 Cost Analysis: Step Functions RPA vs Traditional RPA")
    print("=" * 60)
    
    # Monthly processing volumes
    documents_per_month = 10000
    avg_steps_per_workflow = 15
    avg_lambda_duration_ms = 5000
    
    # Step Functions costs
    state_transitions = documents_per_month * avg_steps_per_workflow
    step_functions_cost = (state_transitions / 1000) * 0.025
    
    # Lambda costs (assuming 512MB memory)
    lambda_gb_seconds = (documents_per_month * avg_lambda_duration_ms / 1000) * (512 / 1024)
    lambda_cost = lambda_gb_seconds * 0.0000166667
    lambda_requests_cost = (documents_per_month * avg_steps_per_workflow / 8) * 0.0000002  # Assuming 8 Lambda calls per workflow
    
    # Other AWS service costs (estimated)
    s3_cost = 10  # Storage and requests
    sqs_cost = 5   # Queue operations
    sns_cost = 2   # Notifications
    dynamodb_cost = 8  # Logging table
    
    total_step_functions_cost = step_functions_cost + lambda_cost + lambda_requests_cost + s3_cost + sqs_cost + sns_cost + dynamodb_cost
    
    # Traditional RPA costs (estimated)
    rpa_license_cost = 1500  # Per month for enterprise RPA platform
    infrastructure_cost = 500  # VM/server costs
    maintenance_cost = 300     # Support and maintenance
    
    total_traditional_rpa_cost = rpa_license_cost + infrastructure_cost + maintenance_cost
    
    print(f"📊 Monthly Processing Volume: {documents_per_month:,} documents")
    print(f"")
    print(f"💡 Step Functions RPA Costs:")
    print(f"   Step Functions: ${step_functions_cost:.2f}")
    print(f"   Lambda Compute: ${lambda_cost:.2f}")
    print(f"   Lambda Requests: ${lambda_requests_cost:.2f}")
    print(f"   S3 Storage: ${s3_cost:.2f}")
    print(f"   SQS Queues: ${sqs_cost:.2f}")
    print(f"   SNS Notifications: ${sns_cost:.2f}")
    print(f"   DynamoDB: ${dynamodb_cost:.2f}")
    print(f"   Total: ${total_step_functions_cost:.2f}")
    print(f"")
    print(f"🏢 Traditional RPA Costs:")
    print(f"   RPA Platform License: ${rpa_license_cost:.2f}")
    print(f"   Infrastructure: ${infrastructure_cost:.2f}")
    print(f"   Maintenance: ${maintenance_cost:.2f}")
    print(f"   Total: ${total_traditional_rpa_cost:.2f}")
    print(f"")
    print(f"💰 Monthly Savings: ${total_traditional_rpa_cost - total_step_functions_cost:.2f}")
    print(f"📈 Cost Reduction: {((total_traditional_rpa_cost - total_step_functions_cost) / total_traditional_rpa_cost * 100):.1f}%")

if __name__ == "__main__":
    print("🚀 Step Functions RPA Examples")
    print("Choose an example to run:")
    print("1. Document Processing Examples")
    print("2. Batch Processing Example")
    print("3. Human Review Simulation")
    print("4. Cost Analysis")
    print("5. Run All Examples")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == "1":
        example_document_processing()
    elif choice == "2":
        batch_processing_example()
    elif choice == "3":
        human_review_simulation()
    elif choice == "4":
        cost_analysis_example()
    elif choice == "5":
        example_document_processing()
        batch_processing_example()
        human_review_simulation()
        cost_analysis_example()
    else:
        print("Invalid choice. Please run again with a valid option.")
