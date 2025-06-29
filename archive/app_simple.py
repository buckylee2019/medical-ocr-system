# Medical OCR Application - Direct Nova/Claude Processing
# Simple approach: Upload image → Select model → Get structured medical data

from flask import Flask, render_template, request, jsonify
import boto3
import json
import os
import re
import base64
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError
from PIL import Image
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE')
S3_BUCKET = os.getenv('S3_BUCKET', 'medical-ocr-documents')

# Model Configuration
NOVA_MODEL_ID = 'us.amazon.nova-pro-v1:0'
CLAUDE_MODEL_ID = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

# Initialize AWS clients
def create_aws_session():
    if AWS_PROFILE:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        print(f"✅ Using AWS profile: {AWS_PROFILE}")
    else:
        session = boto3.Session(region_name=AWS_REGION)
        print("✅ Using default AWS credentials")
    return session

aws_session = create_aws_session()
s3_client = aws_session.client('s3')
bedrock_client = aws_session.client('bedrock-runtime')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_with_nova(image_data, extraction_type="comprehensive"):
    """Process medical document with Amazon Nova"""
    try:
        if extraction_type == "comprehensive":
            prompt = """
            Analyze this medical document and extract ALL information into structured JSON format.
            
            Return ONLY valid JSON with this structure:
            {
                "patient_info": {
                    "patient_name": "",
                    "date_of_birth": "",
                    "patient_id": "",
                    "address": "",
                    "phone": ""
                },
                "hospital_info": {
                    "hospital_name": "",
                    "hospital_address": "",
                    "phone_number": "",
                    "department": ""
                },
                "provider_info": {
                    "provider_name": "",
                    "provider_title": "",
                    "license_number": "",
                    "npi": ""
                },
                "visit_info": {
                    "issue_date": "",
                    "service_date": "",
                    "visit_type": ""
                },
                "clinical_info": {
                    "diagnosis": "",
                    "medications": [],
                    "dosages": [],
                    "instructions": "",
                    "vital_signs": {}
                },
                "additional_notes": ""
            }
            
            Extract all visible text and organize appropriately. Leave empty strings for missing information.
            Return only JSON, no markdown formatting.
            """
        else:
            prompt = f"""
            Extract {extraction_type} information from this medical document.
            Return structured JSON data relevant to {extraction_type}.
            Focus only on {extraction_type} related content.
            Return only JSON, no markdown.
            """

        # Call Nova
        response = bedrock_client.converse(
            modelId=NOVA_MODEL_ID,
            messages=[{
                "role": "user",
                "content": [
                    {"text": prompt},
                    {"image": {"format": "png", "source": {"bytes": image_data}}}
                ]
            }],
            inferenceConfig={"maxTokens": 2000, "temperature": 0.1}
        )

        response_text = response['output']['message']['content'][0]['text']
        return parse_json_response(response_text, "Nova")

    except Exception as e:
        return {"success": False, "error": f"Nova processing failed: {str(e)}"}

def process_with_claude(image_data, extraction_type="comprehensive"):
    """Process medical document with Claude 3.5 Sonnet"""
    try:
        if extraction_type == "comprehensive":
            prompt = """
            Analyze this medical document image and extract all medical information into a structured JSON format.
            
            Please return ONLY a valid JSON object with this structure:
            {
                "patient_info": {
                    "patient_name": "",
                    "date_of_birth": "",
                    "patient_id": "",
                    "address": "",
                    "phone": ""
                },
                "hospital_info": {
                    "hospital_name": "",
                    "hospital_address": "",
                    "phone_number": "",
                    "department": ""
                },
                "provider_info": {
                    "provider_name": "",
                    "provider_title": "",
                    "license_number": "",
                    "npi": ""
                },
                "visit_info": {
                    "issue_date": "",
                    "service_date": "",
                    "visit_type": ""
                },
                "clinical_info": {
                    "diagnosis": "",
                    "medications": [],
                    "dosages": [],
                    "instructions": "",
                    "vital_signs": {}
                },
                "additional_notes": ""
            }
            
            Extract all visible text and organize it into the appropriate fields. Use empty strings or arrays for missing information.
            Return only the JSON object, no additional text or markdown formatting.
            """
        else:
            prompt = f"""
            Extract {extraction_type} information from this medical document.
            Return structured JSON data relevant to {extraction_type}.
            Focus only on {extraction_type} related content.
            Return only JSON, no markdown.
            """

        # Prepare image for Claude
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Call Claude
        response = bedrock_client.converse(
            modelId=CLAUDE_MODEL_ID,
            messages=[{
                "role": "user",
                "content": [
                    {"text": prompt},
                    {
                        "image": {
                            "format": "png",
                            "source": {"bytes": image_data}
                        }
                    }
                ]
            }],
            inferenceConfig={"maxTokens": 2000, "temperature": 0.1}
        )

        response_text = response['output']['message']['content'][0]['text']
        return parse_json_response(response_text, "Claude")

    except Exception as e:
        return {"success": False, "error": f"Claude processing failed: {str(e)}"}

def parse_json_response(response_text, model_name):
    """Parse JSON response with fallback handling"""
    try:
        # Try direct JSON parsing
        extracted_data = json.loads(response_text)
        return {
            "success": True,
            "model": model_name,
            "extracted_data": extracted_data,
            "raw_response": response_text
        }
    except json.JSONDecodeError:
        try:
            # Handle markdown-wrapped JSON
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                extracted_data = json.loads(json_str)
                return {
                    "success": True,
                    "model": model_name,
                    "extracted_data": extracted_data,
                    "raw_response": response_text,
                    "parsing_method": "markdown_extraction"
                }
            else:
                # Try to find JSON-like content
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    extracted_data = json.loads(json_str)
                    return {
                        "success": True,
                        "model": model_name,
                        "extracted_data": extracted_data,
                        "raw_response": response_text,
                        "parsing_method": "regex_extraction"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Could not extract JSON from response",
                        "raw_response": response_text,
                        "model": model_name
                    }
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "JSON parsing failed",
                "raw_response": response_text,
                "model": model_name
            }

# Routes
@app.route('/')
def index():
    return render_template('simple_ocr.html')

@app.route('/upload_and_process', methods=['POST'])
def upload_and_process():
    """Upload document and process with selected model"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400
    
    try:
        # Get processing parameters
        model_choice = request.form.get('model', 'nova')  # nova or claude
        extraction_type = request.form.get('extraction_type', 'comprehensive')
        
        # Read and process file
        file_data = file.read()
        session_id = str(uuid.uuid4())
        
        # Store in S3
        s3_key = f"uploads/{session_id}/{secure_filename(file.filename)}"
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_data, ContentType=file.content_type)
        
        # Process with selected model
        if model_choice == 'claude':
            result = process_with_claude(file_data, extraction_type)
        else:
            result = process_with_nova(file_data, extraction_type)
        
        # Save results
        if result.get('success'):
            results_key = f"results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=results_key,
                Body=json.dumps({
                    'session_id': session_id,
                    'filename': secure_filename(file.filename),
                    'model_used': model_choice,
                    'extraction_type': extraction_type,
                    'processed_at': datetime.now().isoformat(),
                    'result': result
                }, indent=2),
                ContentType='application/json'
            )
        
        # Prepare image for display
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        file_type = file.content_type.split('/')[-1]
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': secure_filename(file.filename),
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'model_used': model_choice,
            'extraction_type': extraction_type,
            'result': result
        })
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting Medical OCR Application")
    print("📍 Access at: http://localhost:5005")
    print("🤖 Models available: Nova, Claude 3.5 Sonnet")
    app.run(debug=True, host='0.0.0.0', port=5005)
