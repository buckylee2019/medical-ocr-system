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
from PIL import Image, ImageDraw
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE')
S3_BUCKET = os.getenv('S3_BUCKET', 'medical-ocr-documents')
BEDROCK_MODEL_ID = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

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

def crop_image_block(image_data, block_coordinates):
    """Crop a specific block from the image based on coordinates"""
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(image_data))
        
        # Extract coordinates (x, y, width, height as percentages)
        x_percent = block_coordinates['x']
        y_percent = block_coordinates['y'] 
        width_percent = block_coordinates['width']
        height_percent = block_coordinates['height']
        
        # Convert percentages to actual pixels
        img_width, img_height = image.size
        x = int(x_percent * img_width / 100)
        y = int(y_percent * img_height / 100)
        width = int(width_percent * img_width / 100)
        height = int(height_percent * img_height / 100)
        
        # Crop the image
        cropped_image = image.crop((x, y, x + width, y + height))
        
        # Convert back to bytes
        output_buffer = io.BytesIO()
        cropped_image.save(output_buffer, format='PNG')
        return output_buffer.getvalue()
        
    except Exception as e:
        print(f"Error cropping image: {str(e)}")
        return None

def process_block_with_nova(image_data, block_type="general", block_label=""):
    """Process a specific image block with Amazon Nova"""
    try:
        # Create targeted prompt based on block type
        if block_type == "patient_info":
            prompt = f"""
            Extract patient information from this medical document block labeled '{block_label}'. 
            Return ONLY a valid JSON object:
            {{
                "patient_name": "",
                "date_of_birth": "",
                "patient_id": "",
                "address": ""
            }}
            Focus only on patient demographic information. Return only JSON, no markdown.
            """
        elif block_type == "hospital_info":
            prompt = f"""
            Extract hospital/facility information from this medical document block labeled '{block_label}'.
            Return ONLY a valid JSON object:
            {{
                "hospital_name": "",
                "hospital_address": "",
                "phone_number": "",
                "department": ""
            }}
            Focus only on hospital/facility information. Return only JSON, no markdown.
            """
        elif block_type == "provider_info":
            prompt = f"""
            Extract healthcare provider information from this medical document block labeled '{block_label}'.
            Return ONLY a valid JSON object:
            {{
                "provider_name": "",
                "provider_title": "",
                "license_number": "",
                "signature": ""
            }}
            Focus only on healthcare provider information. Return only JSON, no markdown.
            """
        elif block_type == "diagnosis":
            prompt = f"""
            Extract diagnosis information from this medical document block labeled '{block_label}'.
            Return ONLY a valid JSON object:
            {{
                "primary_diagnosis": "",
                "secondary_diagnosis": [],
                "icd_codes": [],
                "diagnosis_date": ""
            }}
            Focus only on diagnosis information. Return only JSON, no markdown.
            """
        elif block_type == "medications":
            prompt = f"""
            Extract medication information from this medical document block labeled '{block_label}'.
            Return ONLY a valid JSON object:
            {{
                "medications": [],
                "dosages": [],
                "frequencies": [],
                "instructions": ""
            }}
            Focus only on medication information. Return only JSON, no markdown.
            """
        elif block_type == "dates":
            prompt = f"""
            Extract date information from this medical document block labeled '{block_label}'.
            Return ONLY a valid JSON object:
            {{
                "issue_date": "",
                "service_date": "",
                "follow_up_date": "",
                "other_dates": []
            }}
            Focus only on dates. Return only JSON, no markdown.
            """
        else:
            prompt = f"""
            Extract all text from this medical document block labeled '{block_label}'.
            Return ONLY a valid JSON object:
            {{
                "extracted_text": "",
                "block_type": "{block_type}",
                "confidence": ""
            }}
            Return only JSON, no markdown.
            """

        # Prepare the request for Nova
        request_body = {
            "messages": [
                {
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

        # Extract and parse response
        response_text = response['output']['message']['content'][0]['text']
        
        # Parse JSON with markdown handling
        try:
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError:
            try:
                # Handle markdown-wrapped JSON
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    extracted_data = json.loads(json_str)
                else:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        extracted_data = json.loads(json_str)
                    else:
                        extracted_data = {"raw_text": response_text, "parsing_note": "Could not extract JSON"}
            except json.JSONDecodeError:
                extracted_data = {"raw_text": response_text, "parsing_error": "JSON extraction failed"}

        return {
            "success": True,
            "block_type": block_type,
            "block_label": block_label,
            "extracted_data": extracted_data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "block_type": block_type,
            "block_label": block_label
        }

@app.route('/')
def index():
    return render_template('block_ocr.html')

@app.route('/upload_for_blocking', methods=['POST'])
def upload_for_blocking():
    """Upload document and prepare for block selection"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Read file data
            file_data = file.read()
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Convert to base64 for display in browser
            file_base64 = base64.b64encode(file_data).decode('utf-8')
            
            # Store original file data temporarily (in production, use Redis or database)
            # For now, we'll store in S3
            temp_key = f"temp/{session_id}/{secure_filename(file.filename)}"
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=temp_key,
                Body=file_data,
                ContentType=file.content_type
            )
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'filename': secure_filename(file.filename),
                'image_data': f"data:image/{file.content_type.split('/')[-1]};base64,{file_base64}",
                's3_key': temp_key
            })
            
        except Exception as e:
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/process_blocks', methods=['POST'])
def process_blocks():
    """Process selected blocks with Nova OCR"""
    try:
        data = request.json
        session_id = data.get('session_id')
        s3_key = data.get('s3_key')
        blocks = data.get('blocks', [])
        
        if not blocks:
            return jsonify({'error': 'No blocks selected'}), 400
        
        # Download original image from S3
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        original_image_data = response['Body'].read()
        
        # Process each block
        results = []
        for block in blocks:
            # Crop the block from the original image
            cropped_image = crop_image_block(original_image_data, block['coordinates'])
            
            if cropped_image:
                # Process with Nova
                block_result = process_block_with_nova(
                    cropped_image, 
                    block['type'], 
                    block['label']
                )
                results.append(block_result)
            else:
                results.append({
                    "success": False,
                    "error": "Failed to crop block",
                    "block_type": block['type'],
                    "block_label": block['label']
                })
        
        # Combine all results
        combined_data = {
            'session_id': session_id,
            'processed_at': datetime.now().isoformat(),
            'blocks_processed': len(results),
            'block_results': results,
            'status': 'completed'
        }
        
        # Save combined results to S3
        results_key = f"block_results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=results_key,
            Body=json.dumps(combined_data, indent=2),
            ContentType='application/json'
        )
        
        return jsonify({
            'success': True,
            'results': results,
            'combined_data': combined_data,
            's3_results_key': results_key
        })
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
