# Main Auto-Block OCR Application
# This is the cleaned up version with automatic bounding box detection

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
BEDROCK_MODEL_ID = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

# Initialize AWS clients with profile support
def create_aws_session():
    if AWS_PROFILE:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        print(f"✅ Using AWS profile: {AWS_PROFILE}")
    else:
        session = boto3.Session(region_name=AWS_REGION)
        print("✅ Using default AWS credentials")
    return session

# Create session and clients
aws_session = create_aws_session()
s3_client = aws_session.client('s3')
bedrock_client = aws_session.client('bedrock-runtime')
textract_client = aws_session.client('textract')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def auto_generate_bounding_boxes(image_data):
    """Use Textract ONLY for layout detection, not text recognition"""
    try:
        # Use Textract's analyze_document for better layout detection
        response = textract_client.analyze_document(
            Document={'Bytes': image_data},
            FeatureTypes=['LAYOUT']  # Only detect layout, not extract text
        )
        
        auto_blocks = []
        block_id = 1
        
        for block in response['Blocks']:
            # Focus on LAYOUT blocks (text regions) rather than LINE blocks
            if block['BlockType'] in ['LAYOUT_TEXT', 'LAYOUT_TITLE', 'LAYOUT_HEADER', 'LAYOUT_FOOTER']:
                bbox = block['Geometry']['BoundingBox']
                
                # Don't extract text here - let Nova do it later
                auto_block = {
                    'id': f'layout_{block_id}',
                    'text_preview': f"Layout Block {block_id}",  # No text extraction
                    'full_text': '',  # Will be filled by Nova
                    'confidence': round(block.get('Confidence', 95.0), 2),
                    'coordinates': {
                        'x': round(bbox['Left'] * 100, 2),
                        'y': round(bbox['Top'] * 100, 2),
                        'width': round(bbox['Width'] * 100, 2),
                        'height': round(bbox['Height'] * 100, 2)
                    },
                    'suggested_type': classify_layout_block(block['BlockType']),
                    'suggested_label': generate_layout_label(block['BlockType'], block_id),
                    'layout_type': block['BlockType'],
                    'source': 'textract_layout',
                    'selected': False
                }
                auto_blocks.append(auto_block)
                block_id += 1
        
        # If no LAYOUT blocks found, fall back to LINE detection for bounding boxes only
        if not auto_blocks:
            auto_blocks = detect_text_regions_only(response)
        
        return {
            'success': True,
            'blocks': auto_blocks,
            'total_blocks': len(auto_blocks),
            'message': f'✅ Auto-detected {len(auto_blocks)} layout regions (text extraction will be done by Nova)'
        }
        
    except Exception as e:
        print(f"❌ Textract layout detection error: {str(e)}")
        # Fallback: try basic text detection for bounding boxes only
        try:
            return fallback_layout_detection(image_data)
        except:
            return {
                'success': False,
                'error': str(e),
                'blocks': [],
                'message': '⚠️ Layout detection failed, you can create blocks manually'
            }

def detect_text_regions_only(textract_response):
    """Extract bounding boxes from LINE blocks without using their text"""
    auto_blocks = []
    block_id = 1
    
    for block in textract_response['Blocks']:
        if block['BlockType'] == 'LINE':
            bbox = block['Geometry']['BoundingBox']
            
            auto_block = {
                'id': f'region_{block_id}',
                'text_preview': f"Text Region {block_id}",  # Generic label
                'full_text': '',  # Will be filled by Nova
                'confidence': round(block.get('Confidence', 90.0), 2),
                'coordinates': {
                    'x': round(bbox['Left'] * 100, 2),
                    'y': round(bbox['Top'] * 100, 2),
                    'width': round(bbox['Width'] * 100, 2),
                    'height': round(bbox['Height'] * 100, 2)
                },
                'suggested_type': 'general',  # Will be classified by Nova
                'suggested_label': f"Text Region {block_id}",
                'layout_type': 'TEXT_REGION',
                'source': 'textract_region',
                'selected': False
            }
            auto_blocks.append(auto_block)
            block_id += 1
    
    return auto_blocks

def fallback_layout_detection(image_data):
    """Fallback layout detection using basic Textract"""
    response = textract_client.detect_document_text(Document={'Bytes': image_data})
    blocks = detect_text_regions_only(response)
    
    return {
        'success': True,
        'blocks': blocks,
        'total_blocks': len(blocks),
        'message': f'✅ Detected {len(blocks)} text regions using fallback method'
    }

def classify_layout_block(layout_type):
    """Classify blocks based on Textract's layout detection"""
    layout_mapping = {
        'LAYOUT_TITLE': 'header_info',
        'LAYOUT_HEADER': 'header_info', 
        'LAYOUT_TEXT': 'general',
        'LAYOUT_FOOTER': 'footer_info',
        'TEXT_REGION': 'general'
    }
    return layout_mapping.get(layout_type, 'general')

def generate_layout_label(layout_type, block_id):
    """Generate labels based on layout type"""
    layout_labels = {
        'LAYOUT_TITLE': f'Title Section {block_id}',
        'LAYOUT_HEADER': f'Header Section {block_id}',
        'LAYOUT_TEXT': f'Text Block {block_id}',
        'LAYOUT_FOOTER': f'Footer Section {block_id}',
        'TEXT_REGION': f'Text Region {block_id}'
    }
    return layout_labels.get(layout_type, f'Layout Block {block_id}')

def classify_text_block(text):
    """This function is now only used for Nova-extracted text classification"""
    # This will be called after Nova extracts the text, not from Textract
    text_lower = text.lower().strip()
    
    # Classification patterns (same as before)
    patterns = {
        'patient_info': ['patient', 'name:', 'dob', 'date of birth', 'mr#', 'mrn', 'id:', 'address'],
        'hospital_info': ['hospital', 'medical center', 'clinic', 'facility', 'department'],
        'provider_info': ['dr.', 'doctor', 'physician', 'md', 'provider', 'attending'],
        'diagnosis': ['diagnosis', 'condition', 'icd', 'primary', 'secondary', 'impression'],
        'medications': ['medication', 'prescription', 'rx', 'mg', 'dosage', 'tablet', 'ml'],
        'vitals': ['bp', 'blood pressure', 'temp', 'temperature', 'pulse', 'weight', 'height']
    }
    
    for block_type, keywords in patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            return block_type
    
    # Check for date patterns
    date_patterns = [r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', r'\d{4}[/-]\d{1,2}[/-]\d{1,2}']
    if any(re.search(pattern, text) for pattern in date_patterns):
        return 'dates'
    
    return 'general'

def generate_block_label(text):
    """Generate label from Nova-extracted text, not Textract text"""
    if not text or text.startswith('Layout Block') or text.startswith('Text Region'):
        return text  # Keep layout-based labels
    
    text_clean = re.sub(r'[^\w\s]', ' ', text.strip()[:30])
    text_clean = ' '.join(text_clean.split())
    return text_clean if text_clean else "Text Block"

def crop_image_block(image_data, coordinates):
    """Crop a specific block from the image"""
    try:
        image = Image.open(io.BytesIO(image_data))
        img_width, img_height = image.size
        
        x = int(coordinates['x'] * img_width / 100)
        y = int(coordinates['y'] * img_height / 100)
        width = int(coordinates['width'] * img_width / 100)
        height = int(coordinates['height'] * img_height / 100)
        
        # Ensure coordinates are within bounds
        x = max(0, min(x, img_width))
        y = max(0, min(y, img_height))
        width = max(1, min(width, img_width - x))
        height = max(1, min(height, img_height - y))
        
        cropped_image = image.crop((x, y, x + width, y + height))
        
        output_buffer = io.BytesIO()
        cropped_image.save(output_buffer, format='PNG')
        return output_buffer.getvalue()
        
    except Exception as e:
        print(f"❌ Error cropping image: {str(e)}")
        return None

def process_block_with_nova(image_data, block_type="general", block_label=""):
    """Process image block with Nova - both text extraction AND intelligent classification"""
    try:
        # First, let Nova extract and classify the text intelligently
        classification_prompt = f"""
        Analyze this medical document block and:
        1. Extract all visible text
        2. Classify the content type
        3. Return structured data
        
        Return ONLY valid JSON:
        {{
            "extracted_text": "all visible text here",
            "content_type": "patient_info|hospital_info|provider_info|diagnosis|medications|dates|vitals|general",
            "confidence": "high|medium|low",
            "structured_data": {{}}
        }}
        
        For structured_data, use appropriate fields based on content_type:
        - patient_info: {{"patient_name": "", "dob": "", "id": "", "address": ""}}
        - hospital_info: {{"hospital_name": "", "address": "", "phone": "", "department": ""}}
        - provider_info: {{"provider_name": "", "title": "", "license": "", "npi": ""}}
        - diagnosis: {{"primary": "", "secondary": [], "icd_codes": [], "date": ""}}
        - medications: {{"medications": [], "dosages": [], "frequencies": [], "instructions": ""}}
        - dates: {{"issue_date": "", "service_date": "", "follow_up": "", "other_dates": []}}
        - vitals: {{"bp": "", "temp": "", "pulse": "", "weight": "", "height": ""}}
        - general: {{"text": "", "category": ""}}
        
        Return only JSON, no markdown.
        """

        # Call Nova for intelligent extraction and classification
        response = bedrock_client.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=[{
                "role": "user",
                "content": [
                    {"text": classification_prompt},
                    {"image": {"format": "png", "source": {"bytes": image_data}}}
                ]
            }],
            inferenceConfig={"maxTokens": 1500, "temperature": 0.1}
        )

        response_text = response['output']['message']['content'][0]['text']
        
        # Parse Nova's response
        try:
            nova_result = json.loads(response_text)
        except json.JSONDecodeError:
            # Handle markdown-wrapped JSON
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
            if json_match:
                nova_result = json.loads(json_match.group(1).strip())
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                nova_result = json.loads(json_match.group(0)) if json_match else {
                    "extracted_text": response_text,
                    "content_type": "general",
                    "confidence": "low",
                    "structured_data": {"text": response_text}
                }

        # Use Nova's classification if it's more specific than the original guess
        detected_type = nova_result.get('content_type', block_type)
        extracted_text = nova_result.get('extracted_text', '')
        
        return {
            "success": True,
            "block_type": detected_type,  # Use Nova's classification
            "block_label": generate_block_label(extracted_text) if extracted_text else block_label,
            "original_type_guess": block_type,  # Keep original layout-based guess
            "extracted_text": extracted_text,
            "nova_confidence": nova_result.get('confidence', 'unknown'),
            "extracted_data": nova_result.get('structured_data', {}),
            "classification_changed": detected_type != block_type
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "block_type": block_type,
            "block_label": block_label
        }

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_and_detect', methods=['POST'])
def upload_and_detect():
    """Upload document and auto-generate bounding boxes"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400
    
    try:
        file_data = file.read()
        session_id = str(uuid.uuid4())
        
        # Store in S3
        s3_key = f"temp/{session_id}/{secure_filename(file.filename)}"
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_data, ContentType=file.content_type)
        
        # Auto-generate blocks
        detection_result = auto_generate_bounding_boxes(file_data)
        
        # Prepare image for display
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        file_type = file.content_type.split('/')[-1]
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': secure_filename(file.filename),
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            's3_key': s3_key,
            'auto_blocks': detection_result['blocks'],
            'detection_success': detection_result['success'],
            'message': detection_result['message'],
            'total_blocks': detection_result['total_blocks']
        })
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/process_blocks', methods=['POST'])
def process_blocks():
    """Process selected blocks with Nova"""
    try:
        data = request.json
        session_id = data.get('session_id')
        s3_key = data.get('s3_key')
        selected_blocks = data.get('selected_blocks', [])
        
        if not selected_blocks:
            return jsonify({'error': 'No blocks selected'}), 400
        
        # Download original image
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        original_image_data = response['Body'].read()
        
        # Process each block
        results = []
        for block in selected_blocks:
            cropped_image = crop_image_block(original_image_data, block['coordinates'])
            
            if cropped_image:
                result = process_block_with_nova(
                    cropped_image, 
                    block.get('type', 'general'), 
                    block.get('label', 'Block')
                )
                result['block_id'] = block['id']
                result['original_text'] = block.get('text_preview', '')
                results.append(result)
            else:
                results.append({
                    "success": False,
                    "error": "Failed to crop block",
                    "block_id": block['id']
                })
        
        # Save results
        results_key = f"results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=results_key,
            Body=json.dumps({
                'session_id': session_id,
                'processed_at': datetime.now().isoformat(),
                'results': results
            }, indent=2),
            ContentType='application/json'
        )
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total': len(results),
                'successful': len([r for r in results if r.get('success')]),
                'failed': len([r for r in results if not r.get('success')])
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting Auto-Block Medical OCR Application")
    print("📍 Access at: http://localhost:5005")
    app.run(debug=True, host='0.0.0.0', port=5005)
