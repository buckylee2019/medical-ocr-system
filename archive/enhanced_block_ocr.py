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
BEDROCK_MODEL_ID = 'us.amazon.nova-pro-v1:0'

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
textract_client = aws_session.client('textract')

def detect_blocks_with_textract(image_data):
    """Use Amazon Textract to automatically detect text blocks"""
    try:
        # Call Textract to detect document text
        response = textract_client.detect_document_text(
            Document={'Bytes': image_data}
        )
        
        detected_blocks = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE' and block.get('Text'):
                bbox = block['Geometry']['BoundingBox']
                
                # Convert Textract coordinates (0-1 range) to percentages
                detected_block = {
                    'id': block['Id'],
                    'text': block['Text'],
                    'confidence': block['Confidence'],
                    'coordinates': {
                        'x': bbox['Left'] * 100,  # Convert to percentage
                        'y': bbox['Top'] * 100,
                        'width': bbox['Width'] * 100,
                        'height': bbox['Height'] * 100
                    },
                    'suggested_type': classify_text_block(block['Text']),
                    'source': 'textract'
                }
                detected_blocks.append(detected_block)
        
        return {
            'success': True,
            'blocks': detected_blocks,
            'total_blocks': len(detected_blocks)
        }
        
    except Exception as e:
        print(f"Textract error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'blocks': []
        }

def classify_text_block(text):
    """Classify text block based on content patterns"""
    text_lower = text.lower()
    
    # Patient information patterns
    if any(keyword in text_lower for keyword in ['patient', 'name:', 'dob', 'date of birth', 'mr#', 'mrn']):
        return 'patient_info'
    
    # Hospital information patterns
    elif any(keyword in text_lower for keyword in ['hospital', 'medical center', 'clinic', 'facility']):
        return 'hospital_info'
    
    # Provider information patterns
    elif any(keyword in text_lower for keyword in ['dr.', 'doctor', 'physician', 'md', 'provider']):
        return 'provider_info'
    
    # Diagnosis patterns
    elif any(keyword in text_lower for keyword in ['diagnosis', 'condition', 'icd', 'primary', 'secondary']):
        return 'diagnosis'
    
    # Medication patterns
    elif any(keyword in text_lower for keyword in ['medication', 'prescription', 'rx', 'mg', 'dosage', 'tablet']):
        return 'medications'
    
    # Date patterns
    elif any(keyword in text_lower for keyword in ['date', '/', '-', '2024', '2023', '2025']):
        if len([c for c in text if c.isdigit()]) > 4:  # Contains multiple digits
            return 'dates'
    
    return 'general'

@app.route('/')
def index():
    return render_template('enhanced_block_ocr.html')

@app.route('/upload_and_detect', methods=['POST'])
def upload_and_detect():
    """Upload document and automatically detect blocks with Textract"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read file data
        file_data = file.read()
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Convert to base64 for display in browser
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        
        # Store original file data in S3
        temp_key = f"temp/{session_id}/{secure_filename(file.filename)}"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=temp_key,
            Body=file_data,
            ContentType=file.content_type
        )
        
        # Detect blocks with Textract
        textract_result = detect_blocks_with_textract(file_data)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': secure_filename(file.filename),
            'image_data': f"data:image/{file.content_type.split('/')[-1]};base64,{file_base64}",
            's3_key': temp_key,
            'detected_blocks': textract_result['blocks'],
            'textract_success': textract_result['success'],
            'textract_error': textract_result.get('error')
        })
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/process_blocks', methods=['POST'])
def process_blocks():
    """Process selected blocks with Nova OCR (same as before)"""
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
        
        # Process each block (same logic as before)
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

# Include the same helper functions from block_ocr_app.py
def crop_image_block(image_data, block_coordinates):
    """Crop a specific block from the image based on coordinates"""
    try:
        image = Image.open(io.BytesIO(image_data))
        
        x_percent = block_coordinates['x']
        y_percent = block_coordinates['y'] 
        width_percent = block_coordinates['width']
        height_percent = block_coordinates['height']
        
        img_width, img_height = image.size
        x = int(x_percent * img_width / 100)
        y = int(y_percent * img_height / 100)
        width = int(width_percent * img_width / 100)
        height = int(height_percent * img_height / 100)
        
        cropped_image = image.crop((x, y, x + width, y + height))
        
        output_buffer = io.BytesIO()
        cropped_image.save(output_buffer, format='PNG')
        return output_buffer.getvalue()
        
    except Exception as e:
        print(f"Error cropping image: {str(e)}")
        return None

def process_block_with_nova(image_data, block_type="general", block_label=""):
    """Process a specific image block with Amazon Nova (same as before)"""
    # Same implementation as in block_ocr_app.py
    # ... (keeping it concise for this example)
    pass

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
