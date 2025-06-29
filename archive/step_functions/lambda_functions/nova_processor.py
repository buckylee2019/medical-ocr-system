import json
import boto3
import base64
from datetime import datetime
import os

def lambda_handler(event, context):
    """
    Lambda function to process documents with Amazon Nova
    This replaces the RPA OCR processing step
    """
    
    # Initialize AWS clients
    s3_client = boto3.client('s3')
    bedrock_client = boto3.client('bedrock-runtime')
    
    # Extract parameters
    s3_bucket = event['s3_bucket']
    s3_key = event['s3_key']
    document_type = event.get('document_type', 'medical')
    session_id = event['session_id']
    
    try:
        # Download document from S3
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        document_content = response['Body'].read()
        
        # Process with Nova
        extracted_data = process_with_nova(bedrock_client, document_content, document_type)
        
        # Calculate confidence scores
        confidence_scores = calculate_confidence_scores(extracted_data)
        
        # Store intermediate results
        intermediate_key = f"processing/{session_id}/nova_output.json"
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=intermediate_key,
            Body=json.dumps({
                'extracted_data': extracted_data,
                'confidence_scores': confidence_scores,
                'processed_at': datetime.now().isoformat(),
                'session_id': session_id
            }),
            ContentType='application/json'
        )
        
        return {
            'statusCode': 200,
            'extracted_data': extracted_data,
            'confidence_scores': confidence_scores,
            'intermediate_s3_key': intermediate_key,
            'session_id': session_id
        }
        
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'session_id': session_id
        }

def process_with_nova(bedrock_client, document_content, document_type):
    """Process document using Amazon Nova"""
    
    # Medical-specific prompt
    if document_type == "medical":
        prompt = """
        Analyze this medical document and extract the following information in JSON format:
        {
            "patient_name": "",
            "date_of_birth": "",
            "issue_date": "",
            "hospital_name": "",
            "provider_name": "",
            "diagnosis": "",
            "medications": [],
            "dosage": "",
            "instructions": "",
            "notes": "",
            "confidence_indicators": {
                "handwriting_clarity": "high|medium|low",
                "document_completeness": "complete|partial|incomplete",
                "text_legibility": "clear|unclear|mixed"
            }
        }
        
        Extract all visible text and organize it into the appropriate fields:
        - patient_name: Full name of the patient
        - date_of_birth: Patient's birth date
        - issue_date: Date when this document was issued/created
        - hospital_name: Name of the hospital or medical facility
        - provider_name: Name of the doctor or healthcare provider
        - diagnosis: Medical diagnosis or condition
        - medications: List of prescribed medications
        - dosage: Medication dosage information
        - instructions: Treatment or medication instructions
        - notes: Any additional notes or observations
        
        If a field is not present, leave it empty.
        Rate the confidence indicators based on document quality.
        """
    else:
        prompt = "Extract all text from this document and organize it into a structured format."

    try:
        # Prepare request for Nova
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                        {
                            "image": {
                                "format": "png",  # Adjust based on actual format
                                "source": {"bytes": document_content}
                            }
                        }
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": 1000,
                "temperature": 0.1
            }
        }

        # Call Nova
        response = bedrock_client.converse(
            modelId=os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'),
            messages=request_body["messages"],
            inferenceConfig=request_body["inferenceConfig"]
        )

        # Extract response
        response_text = response['output']['message']['content'][0]['text']
        
        # Parse JSON response with markdown handling
        try:
            # First, try direct JSON parsing
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from markdown code blocks
            try:
                import re
                # Look for JSON wrapped in ```json ... ``` or ``` ... ```
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    extracted_data = json.loads(json_str)
                else:
                    # If no code blocks found, try to find JSON-like content
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        extracted_data = json.loads(json_str)
                    else:
                        # Fallback to raw text
                        extracted_data = {"raw_text": response_text, "parsing_note": "Could not extract JSON structure"}
            except json.JSONDecodeError:
                # Final fallback
                extracted_data = {"raw_text": response_text, "parsing_error": "JSON extraction failed"}

        return extracted_data

    except Exception as e:
        print(f"Error calling Nova: {str(e)}")
        return {"error": f"Nova processing failed: {str(e)}"}

def calculate_confidence_scores(extracted_data):
    """Calculate confidence scores based on extracted data quality"""
    
    scores = {
        "overall_confidence": 0.0,
        "field_completeness": 0.0,
        "data_quality": 0.0
    }
    
    if "error" in extracted_data:
        return scores
    
    # Calculate field completeness
    required_fields = ["patient_name", "date_of_service", "provider_name"]
    filled_fields = sum(1 for field in required_fields if extracted_data.get(field))
    scores["field_completeness"] = filled_fields / len(required_fields)
    
    # Calculate data quality based on confidence indicators
    if "confidence_indicators" in extracted_data:
        indicators = extracted_data["confidence_indicators"]
        quality_score = 0.0
        
        # Handwriting clarity
        if indicators.get("handwriting_clarity") == "high":
            quality_score += 0.4
        elif indicators.get("handwriting_clarity") == "medium":
            quality_score += 0.2
            
        # Document completeness
        if indicators.get("document_completeness") == "complete":
            quality_score += 0.3
        elif indicators.get("document_completeness") == "partial":
            quality_score += 0.15
            
        # Text legibility
        if indicators.get("text_legibility") == "clear":
            quality_score += 0.3
        elif indicators.get("text_legibility") == "mixed":
            quality_score += 0.15
            
        scores["data_quality"] = quality_score
    else:
        # Fallback scoring
        scores["data_quality"] = 0.5
    
    # Overall confidence
    scores["overall_confidence"] = (scores["field_completeness"] + scores["data_quality"]) / 2
    
    return scores
