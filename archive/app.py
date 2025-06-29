from flask import Flask, render_template, request, jsonify, redirect, url_for
import boto3
import json
import os
import re
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
import base64
from botocore.exceptions import ClientError

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.getenv('AWS_PROFILE')
S3_BUCKET = os.getenv('S3_BUCKET', 'medical-ocr-documents')
BEDROCK_MODEL_ID = 'us.amazon.nova-pro-v1:0'  # or nova-lite-v1:0

# Initialize AWS clients with profile support
def create_aws_session():
    """Create AWS session with profile support"""
    if AWS_PROFILE:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        print(f"Using AWS profile: {AWS_PROFILE}")
    else:
        session = boto3.Session(region_name=AWS_REGION)
        print("Using default AWS credentials")
    return session

# Create session and clients
aws_session = create_aws_session()
s3_client = aws_session.client('s3')
bedrock_client = aws_session.client('bedrock-runtime')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_document_with_nova(image_data, document_type="medical"):
    """Process document using Amazon Nova for OCR"""
    try:
        # Prepare the prompt based on document type
        if document_type == "medical":
            prompt = """
            Analyze this medical document and extract the following information. Return ONLY a valid JSON object with no additional text or formatting:

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
                "notes": ""
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
            Return only the JSON object, no markdown formatting or code blocks.
            """
        else:
            prompt = "Extract all text from this document and organize it into a structured format."

        # Prepare the request for Nova
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        },
                        {
                            "image": {
                                "format": "png",  # Adjust based on actual format
                                "source": {
                                    "bytes": image_data
                                }
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
            modelId=BEDROCK_MODEL_ID,
            messages=request_body["messages"],
            inferenceConfig=request_body["inferenceConfig"]
        )

        # Extract the response text
        response_text = response['output']['message']['content'][0]['text']
        
        # Try to parse as JSON, with fallback handling for markdown-wrapped JSON
        try:
            # First, try direct JSON parsing
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from markdown code blocks
            try:
                # Look for JSON wrapped in ```json ... ``` or ``` ... ```
                import re
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
        print(f"Error processing document with Nova: {str(e)}")
        return {"error": f"OCR processing failed: {str(e)}"}

def save_to_s3(data, filename):
    """Save processed data to S3"""
    try:
        key = f"processed/{datetime.now().strftime('%Y/%m/%d')}/{filename}"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        return key
    except ClientError as e:
        print(f"Error saving to S3: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Read file data
            file_data = file.read()
            
            # Process with Nova OCR
            extracted_data = process_document_with_nova(file_data)
            
            # Generate session ID for tracking
            session_id = str(uuid.uuid4())
            
            # Store in session or temporary storage (you might want to use Redis or DynamoDB)
            # For now, we'll pass it to the form
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'extracted_data': extracted_data,
                'filename': secure_filename(file.filename)
            })
            
        except Exception as e:
            return jsonify({'error': f'Processing failed: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/form/<session_id>')
def show_form(session_id):
    # In a real app, you'd retrieve the extracted data from storage
    # For now, we'll pass it via URL parameters or session
    return render_template('form.html', session_id=session_id)

@app.route('/save', methods=['POST'])
def save_data():
    try:
        form_data = request.json
        session_id = form_data.get('session_id')
        
        # Add metadata
        final_data = {
            'session_id': session_id,
            'processed_at': datetime.now().isoformat(),
            'form_data': form_data,
            'status': 'human_reviewed'
        }
        
        # Save to S3
        filename = f"{session_id}.json"
        s3_key = save_to_s3(final_data, filename)
        
        if s3_key:
            return jsonify({
                'success': True,
                'message': 'Data saved successfully',
                's3_key': s3_key
            })
        else:
            return jsonify({'error': 'Failed to save to S3'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
