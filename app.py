# Medical OCR Application - Multi-Model Voting System
# Claude 3.5 Sonnet 和 Claude 3 Haiku 各跑兩次，然後投票比對

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
from collections import Counter, defaultdict
import difflib
import asyncio
import concurrent.futures
from decimal import Decimal

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE')
S3_BUCKET = os.getenv('S3_BUCKET', 'medical-ocr-documents')

# Model Configuration - Multi-model voting + Final validation
CLAUDE_SONNET_MODEL_ID = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
CLAUDE_HAIKU_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'
CLAUDE_SONNET_LATEST_MODEL_ID = 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'  # For automatic validation

# DynamoDB Configuration
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'medical-ocr-results')

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
dynamodb = aws_session.resource('dynamodb')
dynamodb_table = dynamodb.Table(DYNAMODB_TABLE_NAME)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_floats_to_decimal(obj):
    """遞歸轉換所有 float 為 Decimal，用於 DynamoDB 存儲"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

def save_to_dynamodb(data, processing_mode, confidence_score=None, human_reviewed=False):
    """Save OCR results to DynamoDB"""
    try:
        # Generate unique ID
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Convert confidence_score to Decimal if it's a float
        if confidence_score is not None:
            confidence_score = Decimal(str(confidence_score))
        
        # Convert all float values in data to Decimal
        converted_data = convert_floats_to_decimal(data)
        
        # Prepare DynamoDB item
        item = {
            'id': record_id,
            'timestamp': timestamp,
            'processing_mode': processing_mode,  # 'automatic' or 'human_review'
            'human_reviewed': human_reviewed,
            'data': converted_data,
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # Only add confidence_score if it's not None
        if confidence_score is not None:
            item['confidence_score'] = confidence_score
        
        # Save to DynamoDB
        response = dynamodb_table.put_item(Item=item)
        
        return {
            'success': True,
            'record_id': record_id,
            'timestamp': timestamp,
            'dynamodb_response': response
        }
        
    except Exception as e:
        print(f"❌ DynamoDB 存儲錯誤: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def process_with_claude_latest(image_data, for_human_review=False):
    """Process with Claude 3.7 Sonnet for final validation or human review"""
    try:
        if for_human_review:
            prompt = """
            請分析這份醫療診斷證明書並提取所有資訊，以結構化的 JSON 格式返回。
            這個結果將提供給人工審核，請確保提取的資訊準確且完整。
            
            請返回以下格式的 JSON（只返回 JSON，不要其他格式）：
            {
                "certificate_info": {
                    "certificate_no": "",
                    "certificate_date": ""
                },
                "patient_info": {
                    "name": "",
                    "sex": "",
                    "date_of_birth": "",
                    "nationality": "",
                    "passport_no_or_id": "",
                    "medical_history_no": "",
                    "address": ""
                },
                "examination_info": {
                    "date_of_examination": "",
                    "department": ""
                },
                "medical_content": {
                    "diagnosis": "",
                    "doctors_comment": ""
                },
                "hospital_info": {
                    "hospital_name_chinese": "",
                    "hospital_name_english": "",
                    "superintendent": "",
                    "attending_physician": ""
                },
                "additional_info": {
                    "stamp_or_seal": "",
                    "other_notes": ""
                }
            }
            
            請仔細提取所有可見的文字並適當地組織到相應的欄位中。
            如果某個欄位沒有資訊，請留空字串。
            只返回 JSON，不要 markdown 格式。
            """
        else:
            prompt = get_medical_extraction_prompt()

        # Call Claude 3.7 Sonnet
        response = bedrock_client.converse(
            modelId=CLAUDE_SONNET_LATEST_MODEL_ID,
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
        extracted_data = parse_json_response(response_text)
        
        return {
            "success": True,
            "model": "claude-3.7-sonnet",
            "extracted_data": extracted_data,
            "raw_response": response_text
        }

    except Exception as e:
        return {
            "success": False,
            "model": "claude-3.7-sonnet",
            "error": str(e)
        }

def run_enhanced_voting_system(image_data):
    """Enhanced voting system with Claude 3.7 Sonnet for automatic path"""
    print("🗳️ 開始增強型多模型投票處理...")
    
    # 準備所有任務 - 包含 Claude 3.7 Sonnet
    tasks = [
        # Claude 3.5 Sonnet 跑一次
        (CLAUDE_SONNET_MODEL_ID, 1),
        # Claude 3 Haiku 跑一次  
        (CLAUDE_HAIKU_MODEL_ID, 1),
        # Claude 3.7 Sonnet 跑一次
        (CLAUDE_SONNET_LATEST_MODEL_ID, 1)
    ]
    
    results = []
    
    # 依序執行每個任務
    for model_id, run_number in tasks:
        print(f"🤖 執行 {model_id} - 第 {run_number} 次...")
        try:
            result = process_with_claude_model(image_data, model_id, run_number)
            results.append(result)
            if result.get('success'):
                print(f"✅ {model_id} 處理成功")
            else:
                print(f"❌ {model_id} 處理失敗: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ {model_id} 執行異常: {str(e)}")
            results.append({
                "success": False,
                "model": model_id,
                "run_number": run_number,
                "error": str(e)
            })
    
    # 分析結果並投票
    print("📊 開始分析和投票...")
    voting_result = analyze_and_vote(results)
    
    # 生成摘要
    summary = generate_summary(results, voting_result)
    
    return {
        "individual_results": results,
        "voting_result": voting_result,
        "summary": summary
    }

def get_medical_extraction_prompt():
    """根據診斷證明書表格結構的醫療文件提取提示詞"""
    return """
    請分析這份醫療診斷證明書並提取所有資訊，以結構化的 JSON 格式返回。

    請返回以下格式的 JSON（只返回 JSON，不要其他格式）：
    {
        "certificate_info": {
            "certificate_no": "",
            "certificate_date": ""
        },
        "patient_info": {
            "name": "",
            "sex": "",
            "date_of_birth": "",
            "nationality": "",
            "passport_no_or_id": "",
            "medical_history_no": "",
            "address": ""
        },
        "examination_info": {
            "date_of_examination": "",
            "department": ""
        },
        "medical_content": {
            "diagnosis": "",
            "doctors_comment": ""
        },
        "hospital_info": {
            "hospital_name_chinese": "",
            "hospital_name_english": "",
            "superintendent": "",
            "attending_physician": ""
        },
        "additional_info": {
            "stamp_or_seal": "",
            "other_notes": ""
        }
    }

    請仔細提取所有可見的文字並適當地組織到相應的欄位中：
    - certificate_no: 證明書編號
    - name: 姓名
    - sex: 性別
    - date_of_birth: 出生日期
    - nationality: 國籍
    - passport_no_or_id: 身分證號碼或護照號碼
    - medical_history_no: 病歷號碼
    - address: 住址
    - date_of_examination: 診療日期
    - department: 診療科別
    - diagnosis: 診斷內容
    - doctors_comment: 醫師意見
    - hospital_name_chinese: 醫療院所名稱（中文）
    - hospital_name_english: 醫療院所名稱（英文）
    - superintendent: 院長
    - attending_physician: 主治醫師
    - certificate_date: 證明書日期

    如果某個欄位沒有資訊，請留空字串。
    只返回 JSON，不要 markdown 格式。
    """

def process_with_claude_model(image_data, model_id, run_number):
    """使用指定的 Claude 模型處理醫療文件"""
    try:
        prompt = get_medical_extraction_prompt()
        
        # Call Claude
        response = bedrock_client.converse(
            modelId=model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"text": prompt},
                    {"image": {"format": "png", "source": {"bytes": image_data}}}
                ]
            }],
            inferenceConfig={"maxTokens": 2000, "temperature": 0.5}
        )

        response_text = response['output']['message']['content'][0]['text']
        
        # Parse JSON response
        extracted_data = parse_json_response(response_text)
        
        return {
            "success": True,
            "model": model_id,
            "run_number": run_number,
            "extracted_data": extracted_data,
            "raw_response": response_text
        }

    except Exception as e:
        return {
            "success": False,
            "model": model_id,
            "run_number": run_number,
            "error": str(e)
        }

def parse_json_response(response_text):
    """解析 JSON 回應"""
    try:
        # 直接解析 JSON
        return json.loads(response_text)
    except json.JSONDecodeError:
        try:
            # 處理 markdown 包裝的 JSON
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                return json.loads(json_str)
            else:
                # 嘗試找到 JSON 內容
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    return json.loads(json_str)
                else:
                    return {"raw_text": response_text, "parsing_error": "無法提取 JSON"}
        except json.JSONDecodeError:
            return {"raw_text": response_text, "parsing_error": "JSON 解析失敗"}

def run_multi_model_voting(image_data):
    """執行多模型投票系統"""
    print("🗳️ 開始多模型投票處理...")
    
    # 準備所有任務
    tasks = [
        # Claude 3.5 Sonnet 跑兩次
        (CLAUDE_SONNET_MODEL_ID, 1),
        (CLAUDE_SONNET_MODEL_ID, 2),
        # Claude 3 Haiku 跑兩次
        (CLAUDE_HAIKU_MODEL_ID, 1),
        (CLAUDE_HAIKU_MODEL_ID, 2)
    ]
    
    results = []
    
    # 依序執行每個任務
    for model_id, run_number in tasks:
        print(f"🤖 執行 {model_id} - 第 {run_number} 次...")
        result = process_with_claude_model(image_data, model_id, run_number)
        results.append(result)
    
    # 分析結果並投票
    voting_result = analyze_and_vote(results)
    
    return {
        "individual_results": results,
        "voting_result": voting_result,
        "summary": generate_summary(results, voting_result)
    }

def analyze_and_vote(results):
    """分析結果並進行投票"""
    print("📊 分析結果並進行投票...")
    
    successful_results = [r for r in results if r.get('success')]
    
    if not successful_results:
        print("❌ 所有模型都處理失敗")
        return {
            "error": "所有模型都處理失敗",
            "final_result": {},
            "vote_details": {},
            "successful_models": 0,
            "total_models": len(results)
        }
    
    print(f"✅ {len(successful_results)}/{len(results)} 個模型處理成功")
    
    # 收集所有欄位的值
    field_votes = defaultdict(list)
    
    for result in successful_results:
        data = result.get('extracted_data', {})
        if not data:
            print(f"⚠️ 模型 {result.get('model', 'unknown')} 沒有提取到資料")
            continue
        
        # 調試：打印每個模型提取的資料結構
        print(f"🔍 模型 {result.get('model', 'unknown')} 提取的資料:")
        for section, content in data.items():
            if isinstance(content, dict):
                non_empty_fields = [k for k, v in content.items() if v]
                print(f"  - {section}: {len(content)} 個欄位, {len(non_empty_fields)} 個有值")
            else:
                print(f"  - {section}: {type(content)}")
        
        collect_field_votes(data, field_votes, result['model'], result['run_number'])
    
    if not field_votes:
        print("❌ 沒有收集到任何欄位資料")
        return {
            "error": "沒有收集到任何欄位資料",
            "final_result": {},
            "vote_details": {},
            "successful_models": len(successful_results),
            "total_models": len(results)
        }
    
    # 對每個欄位進行投票
    final_result = {}
    vote_details = {}
    
    for field_path, votes in field_votes.items():
        winner, vote_detail = vote_for_field(votes)
        set_nested_field(final_result, field_path, winner)
        vote_details[field_path] = vote_detail
    
    print(f"✅ 投票完成，處理了 {len(vote_details)} 個欄位")
    
    return {
        "final_result": final_result,
        "vote_details": vote_details,
        "successful_models": len(successful_results),
        "total_models": len(results)
    }

def collect_field_votes(data, field_votes, model, run_number, prefix=""):
    """收集欄位投票"""
    for key, value in data.items():
        field_path = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            collect_field_votes(value, field_votes, model, run_number, field_path)
        elif isinstance(value, list):
            # 對於陣列，轉換為字串進行投票
            field_votes[field_path].append({
                'value': json.dumps(value, ensure_ascii=False),
                'model': model,
                'run': run_number
            })
        else:
            field_votes[field_path].append({
                'value': str(value) if value else "",
                'model': model,
                'run': run_number
            })

def vote_for_field(votes):
    """對單一欄位進行投票"""
    if not votes:
        return "", {"winner": "", "votes": [], "confidence": 0}
    
    # 統計投票
    vote_counts = Counter(vote['value'] for vote in votes)
    
    # 找出最高票數
    winner = vote_counts.most_common(1)[0][0]
    winner_count = vote_counts[winner]
    
    # 計算信心度
    confidence = winner_count / len(votes)
    
    return winner, {
        "winner": winner,
        "votes": vote_counts,
        "confidence": confidence,
        "details": votes
    }

def set_nested_field(obj, field_path, value):
    """設置嵌套欄位值"""
    keys = field_path.split('.')
    current = obj
    
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    # 處理陣列值
    final_key = keys[-1]
    if value.startswith('[') and value.endswith(']'):
        try:
            current[final_key] = json.loads(value)
        except:
            current[final_key] = value
    else:
        current[final_key] = value

def generate_summary(individual_results, voting_result):
    """生成摘要報告"""
    successful = len([r for r in individual_results if r.get('success')])
    total = len(individual_results)
    
    model_performance = {}
    for result in individual_results:
        model_name = result['model'].split('.')[-1]  # 簡化模型名稱
        if model_name not in model_performance:
            model_performance[model_name] = {'success': 0, 'total': 0}
        
        model_performance[model_name]['total'] += 1
        if result.get('success'):
            model_performance[model_name]['success'] += 1
    
    # 計算投票信心度
    vote_details = voting_result.get('vote_details', {})
    avg_confidence = sum(detail['confidence'] for detail in vote_details.values()) / len(vote_details) if vote_details else 0
    
    return {
        "total_runs": total,
        "successful_runs": successful,
        "success_rate": successful / total if total > 0 else 0,
        "model_performance": model_performance,
        "average_confidence": avg_confidence,
        "high_confidence_fields": [field for field, detail in vote_details.items() if detail.get('confidence', 0) >= 0.75],
        "low_confidence_fields": [field for field, detail in vote_details.items() if detail.get('confidence', 0) < 0.5]
    }

# Routes
@app.route('/')
def index():
    return render_template('enhanced_voting_ocr.html')

@app.route('/upload_and_vote', methods=['POST'])
def upload_and_vote():
    """上傳文件並執行投票處理 - 原有功能保持不變"""
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': '無效的檔案'}), 400
    
    try:
        # 讀取和處理檔案
        file_data = file.read()
        session_id = str(uuid.uuid4())
        
        # 儲存到 S3
        s3_key = f"voting_uploads/{session_id}/{secure_filename(file.filename)}"
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_data, ContentType=file.content_type)
        
        # 執行多模型投票處理
        voting_results = run_multi_model_voting(file_data)
        
        # 儲存結果
        results_key = f"voting_results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=results_key,
            Body=json.dumps({
                'session_id': session_id,
                'filename': secure_filename(file.filename),
                'processed_at': datetime.now().isoformat(),
                'voting_results': voting_results
            }, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        # 準備圖片顯示
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        file_type = file.content_type.split('/')[-1]
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': secure_filename(file.filename),
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'voting_results': voting_results
        })
        
    except Exception as e:
        return jsonify({'error': f'處理失敗: {str(e)}'}), 500

@app.route('/process_automatic', methods=['POST'])
def process_automatic():
    """路徑1: 全自動處理 - 3個模型投票後直接存入DynamoDB"""
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': '無效的檔案'}), 400
    
    try:
        # 讀取和處理檔案
        file_data = file.read()
        session_id = str(uuid.uuid4())
        
        # 儲存到 S3
        s3_key = f"automatic_uploads/{session_id}/{secure_filename(file.filename)}"
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_data, ContentType=file.content_type)
        
        # 執行增強型投票處理 (3個模型)
        voting_results = run_enhanced_voting_system(file_data)
        
        # 調試：打印投票結果結構
        print("🔍 調試 - 投票結果結構:")
        if voting_results and 'voting_result' in voting_results:
            final_result = voting_results['voting_result'].get('final_result', {})
            print(f"  - final_result 鍵: {list(final_result.keys())}")
            for section, content in final_result.items():
                if isinstance(content, dict):
                    print(f"  - {section}: {list(content.keys())}")
                else:
                    print(f"  - {section}: {type(content)}")
        
        # 檢查投票結果結構
        if not voting_results or 'voting_result' not in voting_results:
            return jsonify({'error': '投票處理失敗：無效的結果結構'}), 500
            
        if 'final_result' not in voting_results['voting_result']:
            return jsonify({'error': '投票處理失敗：缺少最終結果'}), 500
        
        # 計算平均信心度
        vote_details = voting_results['voting_result'].get('vote_details', {})
        avg_confidence = sum(detail['confidence'] for detail in vote_details.values()) / len(vote_details) if vote_details else 0
        
        # 自動存入 DynamoDB
        final_result = voting_results['voting_result']['final_result']
        db_result = save_to_dynamodb(
            data=final_result,
            processing_mode='automatic',
            confidence_score=avg_confidence,
            human_reviewed=False
        )
        
        # 儲存處理結果到 S3
        results_key = f"automatic_results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=results_key,
            Body=json.dumps({
                'session_id': session_id,
                'filename': secure_filename(file.filename),
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'automatic',
                'voting_results': voting_results,
                'dynamodb_result': db_result
            }, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        # 準備圖片顯示
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        file_type = file.content_type.split('/')[-1]
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': secure_filename(file.filename),
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'processing_mode': 'automatic',
            'voting_results': voting_results,
            'dynamodb_result': db_result,
            'confidence_score': avg_confidence
        })
        
    except Exception as e:
        return jsonify({'error': f'自動處理失敗: {str(e)}'}), 500

@app.route('/process_human_review', methods=['POST'])
def process_human_review():
    """路徑2: 人工審核 - Claude 3.7 Sonnet處理後等待人工確認"""
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': '無效的檔案'}), 400
    
    try:
        # 讀取和處理檔案
        file_data = file.read()
        session_id = str(uuid.uuid4())
        
        # 儲存到 S3
        s3_key = f"human_review_uploads/{session_id}/{secure_filename(file.filename)}"
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_data, ContentType=file.content_type)
        
        # 使用 Claude 3.7 Sonnet 處理
        claude_result = process_with_claude_latest(file_data, for_human_review=True)
        
        # 儲存待審核結果到 S3
        pending_key = f"pending_review/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=pending_key,
            Body=json.dumps({
                'session_id': session_id,
                'filename': secure_filename(file.filename),
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'human_review',
                'status': 'pending_review',
                'claude_result': claude_result
            }, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        # 準備圖片顯示
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        file_type = file.content_type.split('/')[-1]
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': secure_filename(file.filename),
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'processing_mode': 'human_review',
            'status': 'pending_review',
            'claude_result': claude_result,
            's3_pending_key': pending_key
        })
        
    except Exception as e:
        return jsonify({'error': f'人工審核處理失敗: {str(e)}'}), 500

@app.route('/submit_human_review', methods=['POST'])
def submit_human_review():
    """提交人工審核後的結果到DynamoDB"""
    try:
        data = request.json
        session_id = data.get('session_id')
        reviewed_data = data.get('reviewed_data')
        
        if not session_id or not reviewed_data:
            return jsonify({'error': '缺少必要參數'}), 400
        
        # 存入 DynamoDB
        db_result = save_to_dynamodb(
            data=reviewed_data,
            processing_mode='human_review',
            confidence_score=Decimal('1.0'),  # 人工審核後信心度設為100%
            human_reviewed=True
        )
        
        # 更新 S3 中的狀態
        final_key = f"human_reviewed/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=final_key,
            Body=json.dumps({
                'session_id': session_id,
                'processed_at': datetime.now().isoformat(),
                'reviewed_at': datetime.now().isoformat(),
                'processing_mode': 'human_review',
                'status': 'completed',
                'reviewed_data': reviewed_data,
                'dynamodb_result': db_result
            }, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'completed',
            'dynamodb_result': db_result
        })
        
    except Exception as e:
        return jsonify({'error': f'提交審核結果失敗: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'models': {
            'claude_3_5_sonnet': CLAUDE_SONNET_MODEL_ID,
            'claude_3_haiku': CLAUDE_HAIKU_MODEL_ID,
            'claude_3_7_sonnet': CLAUDE_SONNET_LATEST_MODEL_ID
        },
        'dynamodb_table': DYNAMODB_TABLE_NAME
    })

@app.route('/debug_models')
def debug_models():
    """Debug endpoint to test model connectivity"""
    return jsonify({
        'models_configured': {
            'claude_3_5_sonnet': CLAUDE_SONNET_MODEL_ID,
            'claude_3_haiku': CLAUDE_HAIKU_MODEL_ID,
            'claude_3_7_sonnet': CLAUDE_SONNET_LATEST_MODEL_ID
        },
        'aws_region': AWS_REGION,
        'aws_profile': AWS_PROFILE,
        's3_bucket': S3_BUCKET,
        'dynamodb_table': DYNAMODB_TABLE_NAME
    })

if __name__ == '__main__':
    print("🚀 啟動醫療 OCR 增強型投票系統")
    print("📍 訪問地址: http://localhost:5006")
    print("🤖 模型: Claude 3.7 Sonnet + Claude 3.5 Sonnet + Claude 3 Haiku")
    print("🗳️ 投票機制: 多模型結果比對和投票")
    print("💾 DynamoDB: 自動存儲處理結果")
    app.run(debug=True, host='0.0.0.0', port=5006)
