# Medical OCR Application - Multi-Model Voting System
# Claude 3.5 Sonnet 和 Claude 3 Haiku 各跑兩次，然後投票比對

from flask import Flask, render_template, request, jsonify, redirect
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

# 日期格式正規化函數
def normalize_date_format(date_string):
    """
    將各種日期格式統一轉換為 yyyy/mm/dd 格式
    支持的輸入格式包括：
    - yyyy-mm-dd, yyyy/mm/dd, yyyy.mm.dd
    - dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy
    - mm-dd-yyyy, mm/dd/yyyy, mm.dd.yyyy
    - yyyy年mm月dd日, yyyy年mm月dd號
    - 民國年格式等
    """
    if not date_string or not isinstance(date_string, str):
        return date_string
    
    # 移除多餘的空白字符
    date_string = date_string.strip()
    
    if not date_string:
        return date_string
    
    try:
        # 處理中文日期格式 (yyyy年mm月dd日, yyyy年mm月dd號)
        chinese_date_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})[日號]?'
        chinese_match = re.search(chinese_date_pattern, date_string)
        if chinese_match:
            year, month, day = chinese_match.groups()
            return f"{year}/{month.zfill(2)}/{day.zfill(2)}"
        
        # 處理民國年格式 (民國xxx年mm月dd日)
        roc_date_pattern = r'民國(\d{1,3})年(\d{1,2})月(\d{1,2})[日號]?'
        roc_match = re.search(roc_date_pattern, date_string)
        if roc_match:
            roc_year, month, day = roc_match.groups()
            year = int(roc_year) + 1911  # 民國年轉西元年
            return f"{year}/{month.zfill(2)}/{day.zfill(2)}"
        
        # 處理各種分隔符的日期格式
        # 匹配 yyyy-mm-dd, yyyy/mm/dd, yyyy.mm.dd 格式
        iso_pattern = r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})'
        iso_match = re.search(iso_pattern, date_string)
        if iso_match:
            year, month, day = iso_match.groups()
            # 驗證是否為合理的日期
            try:
                datetime(int(year), int(month), int(day))
                return f"{year}/{month.zfill(2)}/{day.zfill(2)}"
            except ValueError:
                pass
        
        # 處理 dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy 格式
        dmy_pattern = r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})'
        dmy_match = re.search(dmy_pattern, date_string)
        if dmy_match:
            day, month, year = dmy_match.groups()
            # 驗證是否為合理的日期
            try:
                datetime(int(year), int(month), int(day))
                return f"{year}/{month.zfill(2)}/{day.zfill(2)}"
            except ValueError:
                pass
        
        # 處理 mm-dd-yyyy, mm/dd/yyyy, mm.dd.yyyy 格式 (美式日期)
        mdy_pattern = r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})'
        mdy_match = re.search(mdy_pattern, date_string)
        if mdy_match:
            month, day, year = mdy_match.groups()
            # 驗證是否為合理的日期
            try:
                datetime(int(year), int(month), int(day))
                # 如果月份大於12，可能是dd/mm/yyyy格式
                if int(month) > 12:
                    return f"{year}/{day.zfill(2)}/{month.zfill(2)}"
                else:
                    return f"{year}/{month.zfill(2)}/{day.zfill(2)}"
            except ValueError:
                pass
        
        # 處理純數字格式 (yyyymmdd)
        numeric_pattern = r'^(\d{4})(\d{2})(\d{2})$'
        numeric_match = re.match(numeric_pattern, date_string)
        if numeric_match:
            year, month, day = numeric_match.groups()
            try:
                datetime(int(year), int(month), int(day))
                return f"{year}/{month}/{day}"
            except ValueError:
                pass
        
        # 如果都無法匹配，返回原始字符串
        return date_string
        
    except Exception as e:
        print(f"日期格式化錯誤: {str(e)}")
        return date_string

def normalize_dates_in_data(data):
    """
    遞歸地正規化數據結構中的所有日期字段
    """
    if isinstance(data, dict):
        normalized_data = {}
        for key, value in data.items():
            # 檢查是否為日期相關字段
            if any(date_keyword in key.lower() for date_keyword in ['date', '日期', 'time', '時間']):
                if isinstance(value, str):
                    normalized_data[key] = normalize_date_format(value)
                else:
                    normalized_data[key] = value
            else:
                normalized_data[key] = normalize_dates_in_data(value)
        return normalized_data
    elif isinstance(data, list):
        return [normalize_dates_in_data(item) for item in data]
    else:
        return data

# 動物醫院初診表字段映射
VET_FORM_FIELDS = {
    # 基本資料 Basic Information
    'chart_number': '病歷號碼',
    'first_visit_date': '初診日期',
    
    # 寵物資料 Pet Information
    'pet_name': '寵物名',
    'species': '物種',
    'breed': '品種',
    'pet_gender': '性別',
    'desexed': '絕育',
    'color': '毛色',
    'age_years': '年齡-年',
    'age_months': '年齡-月',
    'age_days': '年齡-日',
    
    # 病史資料 Medical History
    'past_medical_history': '過去病史',
    'drug_allergy': '藥物過敏',
    'allergen_name': '過敏藥物名稱',
    'skin_disease': '皮膚疾病',
    'heartworm_infection': '心絲蟲感染',
    'parasitic_infection': '寄生蟲感染',
    'heart_condition': '心臟疾病',
    'other_diseases': '其他疾病',
    
    # 飼主資料 Owner Information
    'owner_id': '身份證/護照號碼',
    'owner_name': '飼主姓名',
    'owner_birth_date': '出生日期',
    'owner_gender': '性別',
    'phone': '電話',
    'line_id': 'Line ID',
    'email': 'E-mail',
    'registered_address': '戶籍地址',
    'mailing_address': '通訊地址',
    
    # 預防醫療資料 Preventive Care
    'monthly_preventive_treatment': '每月定期施打預防針',
    'monthly_preventive_yes': '每月定期施打預防針-是',
    'monthly_preventive_no': '每月定期施打預防針-否',
    'major_illness_surgery': '重大病史及手術',
    'vaccine_types': '曾施打疫苗類型',
    'vaccine_rabies': '狂犬疫苗',
    'vaccine_3in1': '三合一疫苗',
    'vaccine_4in1': '四合一疫苗',
    'vaccine_5in1': '五合一疫苗',
    'vaccine_others': '其他疫苗',
    'vaccine_others_detail': '其他疫苗詳細內容',
    
    # 就診資訊 Visit Information
    'visit_purpose': '初診目的',
    'remarks': '備註'
}

def normalize_vet_form_data(data):
    """
    正規化動物醫院初診表數據，包含日期格式化和字段驗證
    """
    if not isinstance(data, dict):
        return data
    
    normalized_data = {}
    
    for key, value in data.items():
        # 跳過空值
        if not value or (isinstance(value, str) and not value.strip()):
            normalized_data[key] = value
            continue
            
        # 日期字段特殊處理
        date_fields = ['first_visit_date', 'owner_birth_date']
        if key in date_fields and isinstance(value, str):
            normalized_data[key] = normalize_date_format(value.strip())
        else:
            # 其他字段去除前後空白
            if isinstance(value, str):
                normalized_data[key] = value.strip()
            else:
                normalized_data[key] = value
    
    return normalized_data
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
DYNAMODB_IMAGES_TABLE_NAME = os.getenv('DYNAMODB_IMAGES_TABLE_NAME', 'medical-ocr-images')

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
dynamodb_images_table = dynamodb.Table(DYNAMODB_IMAGES_TABLE_NAME)

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

def save_image_metadata_to_dynamodb(filename, s3_key, file_size, content_type, session_id=None):
    """保存圖片元數據到現有的 DynamoDB 表格"""
    try:
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # 使用現有表格，添加 record_type 來區分數據類型
        item = {
            'id': record_id,
            'record_type': 'image_metadata',  # 區分圖片元數據和OCR結果
            'timestamp': timestamp,
            'filename': filename,
            's3_key': s3_key,
            'file_size': file_size,
            'content_type': content_type,
            'processing_status': 'uploaded',  # uploaded, processing, completed, failed
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        if session_id:
            item['session_id'] = session_id
        
        response = dynamodb_table.put_item(Item=item)
        
        return {
            'success': True,
            'image_id': record_id,
            'timestamp': timestamp
        }
        
    except Exception as e:
        print(f"❌ 圖片元數據存儲錯誤: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def update_image_processing_status(image_id, status, ocr_result_id=None):
    """更新圖片處理狀態"""
    try:
        update_expression = "SET processing_status = :status, updated_at = :updated_at"
        expression_values = {
            ':status': status,
            ':updated_at': datetime.now().isoformat()
        }
        
        if ocr_result_id:
            update_expression += ", ocr_result_id = :ocr_result_id"
            expression_values[':ocr_result_id'] = ocr_result_id
        
        response = dynamodb_table.update_item(
            Key={'id': image_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        return {'success': True}
        
    except Exception as e:
        print(f"❌ 更新圖片狀態錯誤: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_uploaded_images(limit=50):
    """獲取已上傳的圖片列表"""
    try:
        # 使用 scan 操作查找所有圖片元數據記錄
        response = dynamodb_table.scan(
            FilterExpression='record_type = :record_type',
            ExpressionAttributeValues={':record_type': 'image_metadata'},
            Limit=limit
        )
        
        images = []
        for item in response.get('Items', []):
            # 生成預簽名URL用於圖片預覽
            try:
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET, 'Key': item['s3_key']},
                    ExpiresIn=3600  # 1小時有效期
                )
            except:
                presigned_url = None
            
            images.append({
                'id': item['id'],
                'filename': item['filename'],
                's3_key': item['s3_key'],
                'file_size': item['file_size'],
                'content_type': item['content_type'],
                'processing_status': item['processing_status'],
                'created_at': item['created_at'],
                'updated_at': item['updated_at'],
                'session_id': item.get('session_id'),
                'ocr_result_id': item.get('ocr_result_id'),
                'presigned_url': presigned_url
            })
        
        # 按創建時間排序（最新的在前）
        images.sort(key=lambda x: x['created_at'], reverse=True)
        
        return {
            'success': True,
            'images': images,
            'count': len(images)
        }
        
    except Exception as e:
        print(f"❌ 獲取圖片列表錯誤: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'images': [],
            'count': 0
        }
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
        
        # 正規化動物醫院初診表數據
        normalized_data = normalize_vet_form_data(data)
        print(f"🐾 動物醫院初診表數據正規化完成: {json.dumps(normalized_data, indent=2, ensure_ascii=False)}")
        
        # Convert all float values in data to Decimal
        converted_data = convert_floats_to_decimal(normalized_data)
        
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
            請分析這份動物醫院初診表並提取所有資訊，以結構化的 JSON 格式返回。
            這個結果將提供給人工審核，請確保提取的資訊準確且完整。
            
            請返回以下格式的 JSON（只返回 JSON，不要其他格式）：
            {
                "basic_info": {
                    "chart_number": "",
                    "first_visit_date": ""
                },
                "pet_info": {
                    "pet_name": "",
                    "species": "",
                    "breed": "",
                    "pet_gender": "",
                    "desexed": "",
                    "color": "",
                    "age_years": "",
                    "age_months": "",
                    "age_days": ""
                },
                "medical_history": {
                    "past_medical_history": "",
                    "drug_allergy": "",
                    "allergen_name": "",
                    "skin_disease": "",
                    "heartworm_infection": "",
                    "parasitic_infection": "",
                    "heart_condition": "",
                    "other_diseases": ""
                },
                "owner_info": {
                    "owner_id": "",
                    "owner_name": "",
                    "owner_birth_date": "",
                    "owner_gender": "",
                    "phone": "",
                    "line_id": "",
                    "email": "",
                    "registered_address": "",
                    "mailing_address": ""
                },
                "preventive_care": {
                    "monthly_preventive_treatment": "",
                    "monthly_preventive_yes": "",
                    "monthly_preventive_no": "",
                    "major_illness_surgery": "",
                    "vaccine_types": "",
                    "vaccine_rabies": "",
                    "vaccine_3in1": "",
                    "vaccine_4in1": "",
                    "vaccine_5in1": "",
                    "vaccine_others": "",
                    "vaccine_others_detail": ""
                },
                "visit_info": {
                    "visit_purpose": "",
                    "remarks": ""
                }
            }
            
            特別注意：
            1. 寵物年齡請盡可能精確到日，如果表格中有年、月、日的詳細資訊，請分別提取
            2. 預防醫療資料中的勾選框請仔細識別：
               - 每月定期施打預防針：如果勾選"是"填入monthly_preventive_yes，如果勾選"否"填入monthly_preventive_no
               - 疫苗類型：勾選的疫苗類型請在對應欄位填入"已施打"
               - 如果勾選"其他疫苗"，請在vaccine_others_detail中填入具體內容（如：兔用疫苗）
            3. 重大病史及手術：如果顯示"無"請填入"無"，如果有具體內容請詳細填入
            
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
    """根據動物醫院初診表格結構的醫療文件提取提示詞"""
    return """
    請分析這份動物醫院初診表並提取所有資訊，以結構化的 JSON 格式返回。

    請返回以下格式的 JSON（只返回 JSON，不要其他格式）：
    {
        "basic_info": {
            "chart_number": "",
            "first_visit_date": ""
        },
        "pet_info": {
            "pet_name": "",
            "species": "",
            "breed": "",
            "pet_gender": "",
            "desexed": "",
            "color": "",
            "age_years": "",
            "age_months": "",
            "age_days": ""
        },
        "medical_history": {
            "past_medical_history": "",
            "drug_allergy": "",
            "allergen_name": "",
            "skin_disease": "",
            "heartworm_infection": "",
            "parasitic_infection": "",
            "heart_condition": "",
            "other_diseases": ""
        },
        "owner_info": {
            "owner_id": "",
            "owner_name": "",
            "owner_birth_date": "",
            "owner_gender": "",
            "phone": "",
            "line_id": "",
            "email": "",
            "registered_address": "",
            "mailing_address": ""
        },
        "preventive_care": {
            "monthly_preventive_treatment": "",
            "monthly_preventive_yes": "",
            "monthly_preventive_no": "",
            "major_illness_surgery": "",
            "vaccine_types": "",
            "vaccine_rabies": "",
            "vaccine_3in1": "",
            "vaccine_4in1": "",
            "vaccine_5in1": "",
            "vaccine_others": "",
            "vaccine_others_detail": ""
        },
        "visit_info": {
            "visit_purpose": "",
            "remarks": ""
        }
    }

    請仔細提取所有可見的文字並適當地組織到相應的欄位中：

    基本資料 Basic Information:
    - chart_number: 病歷號碼
    - first_visit_date: 初診日期

    寵物資料 Pet Information:
    - pet_name: 寵物名
    - species: 物種（犬/貓/兔/其他）
    - breed: 品種
    - pet_gender: 性別（公/母）
    - desexed: 絕育（是/否）
    - color: 毛色
    - age_years: 年齡-年
    - age_months: 年齡-月
    - age_days: 年齡-日

    病史資料 Medical History:
    - past_medical_history: 過去病史（無/有）
    - drug_allergy: 藥物過敏（無/有）
    - allergen_name: 過敏藥物名稱
    - skin_disease: 皮膚疾病詳情
    - heartworm_infection: 心絲蟲感染詳情
    - parasitic_infection: 寄生蟲感染詳情
    - heart_condition: 心臟疾病詳情
    - other_diseases: 其他疾病詳情

    飼主資料 Owner Information:
    - owner_id: 身份證/護照號碼
    - owner_name: 飼主姓名
    - owner_birth_date: 出生日期
    - owner_gender: 性別（男/女）
    - phone: 電話
    - line_id: Line ID
    - email: E-mail
    - registered_address: 戶籍地址
    - mailing_address: 通訊地址

    預防醫療資料 Preventive Care:
    - monthly_preventive_treatment: 每月定期施打預防針 Monthly Preventive Treatment（整體描述）
    - monthly_preventive_yes: 每月定期施打預防針-是（如果勾選"是"則填入"是"）
    - monthly_preventive_no: 每月定期施打預防針-否（如果勾選"否"則填入"否"）
    - major_illness_surgery: 重大病史及手術 Major Illness or Surgery
    - vaccine_types: 曾施打疫苗類型 Types of Vaccines Given（整體描述）
    - vaccine_rabies: 狂犬疫苗 Rabies（如果勾選則填入"已施打"）
    - vaccine_3in1: 三合一疫苗 3-in-1（如果勾選則填入"已施打"）
    - vaccine_4in1: 四合一疫苗 4-in-1（如果勾選則填入"已施打"）
    - vaccine_5in1: 五合一疫苗 5-in-1（如果勾選則填入"已施打"）
    - vaccine_others: 其他疫苗 Others（如果勾選則填入"已施打"）
    - vaccine_others_detail: 其他疫苗的詳細內容（如：兔用疫苗）

    就診資訊 Visit Information:
    - visit_purpose: 初診目的
    - remarks: 備註

    特別注意：
    1. 寵物年齡請盡可能精確到日，如果表格中有年、月、日的詳細資訊，請分別提取
    2. 預防醫療資料中的勾選框請仔細識別，勾選的項目請標註為相應的值
    3. 疫苗類型如果有勾選"其他"，請特別注意提取其詳細內容
    4. 所有日期格式請保持一致（YYYY-MM-DD或原始格式）
    

    如果某個欄位沒有資訊，請留空字串。
    只返回 JSON，不要 markdown 格式。"""

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

@app.route('/health')
def health_check():
    """Health check endpoint for load balancers and monitoring"""
    try:
        # Test DynamoDB connection
        dynamodb_table.scan(Limit=1)
        
        # Test S3 connection
        s3_client.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=1)
        
        # Test Bedrock connection (use bedrock client instead of bedrock-runtime)
        bedrock_list_client = aws_session.client('bedrock')
        bedrock_list_client.list_foundation_models()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.2.0',
            'services': {
                'dynamodb': 'ok',
                's3': 'ok',
                'bedrock': 'ok'
            },
            'environment': {
                'region': AWS_REGION,
                'table': DYNAMODB_TABLE_NAME,
                'bucket': S3_BUCKET
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'services': {
                'dynamodb': 'unknown',
                's3': 'unknown', 
                'bedrock': 'unknown'
            }
        }), 503

# Routes
@app.route('/')
def index():
    return redirect('/enhanced_voting_ocr')

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
        filename = secure_filename(file.filename)
        
        # 儲存到 S3
        s3_key = f"automatic_uploads/{datetime.now().strftime('%Y/%m/%d')}/{session_id}/{filename}"
        s3_client.put_object(
            Bucket=S3_BUCKET, 
            Key=s3_key, 
            Body=file_data, 
            ContentType=file.content_type,
            Metadata={
                'session_id': session_id,
                'processing_mode': 'automatic',
                'original_filename': filename
            }
        )
        
        # 保存圖片元數據到 DynamoDB
        image_metadata = save_image_metadata_to_dynamodb(
            filename=filename,
            s3_key=s3_key,
            file_size=len(file_data),
            content_type=file.content_type,
            session_id=session_id
        )
        
        if not image_metadata['success']:
            return jsonify({'error': f'圖片元數據保存失敗: {image_metadata["error"]}'}), 500
        
        image_id = image_metadata['image_id']
        
        # 更新處理狀態為 processing
        update_image_processing_status(image_id, 'processing')
        
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
            update_image_processing_status(image_id, 'failed')
            return jsonify({'error': '投票處理失敗：無效的結果結構'}), 500
            
        if 'final_result' not in voting_results['voting_result']:
            update_image_processing_status(image_id, 'failed')
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
        
        # 更新圖片處理狀態
        if db_result['success']:
            update_image_processing_status(image_id, 'completed', db_result['record_id'])
        else:
            update_image_processing_status(image_id, 'failed')
        
        # 儲存處理結果到 S3
        results_key = f"automatic_results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=results_key,
            Body=json.dumps({
                'session_id': session_id,
                'image_id': image_id,
                'filename': filename,
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
            'image_id': image_id,
            'filename': filename,
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'processing_mode': 'automatic',
            'voting_results': voting_results,
            'dynamodb_result': db_result,
            'confidence_score': avg_confidence,
            's3_key': s3_key
        })
        
    except Exception as e:
        # 如果有 image_id，更新狀態為失敗
        if 'image_id' in locals():
            update_image_processing_status(image_id, 'failed')
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
        filename = secure_filename(file.filename)
        
        # 儲存到 S3
        s3_key = f"human_review_uploads/{datetime.now().strftime('%Y/%m/%d')}/{session_id}/{filename}"
        s3_client.put_object(
            Bucket=S3_BUCKET, 
            Key=s3_key, 
            Body=file_data, 
            ContentType=file.content_type,
            Metadata={
                'session_id': session_id,
                'processing_mode': 'human_review',
                'original_filename': filename
            }
        )
        
        # 保存圖片元數據到 DynamoDB
        image_metadata = save_image_metadata_to_dynamodb(
            filename=filename,
            s3_key=s3_key,
            file_size=len(file_data),
            content_type=file.content_type,
            session_id=session_id
        )
        
        if not image_metadata['success']:
            return jsonify({'error': f'圖片元數據保存失敗: {image_metadata["error"]}'}), 500
        
        image_id = image_metadata['image_id']
        
        # 更新處理狀態為 processing
        update_image_processing_status(image_id, 'processing')
        
        # 使用 Claude 3.7 Sonnet 處理
        claude_result = process_with_claude_latest(file_data, for_human_review=True)
        
        if claude_result['success']:
            # 更新狀態為待審核
            update_image_processing_status(image_id, 'pending_review')
        else:
            # 更新狀態為失敗
            update_image_processing_status(image_id, 'failed')
        
        # 儲存待審核結果到 S3
        pending_key = f"pending_review/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=pending_key,
            Body=json.dumps({
                'session_id': session_id,
                'image_id': image_id,
                'filename': filename,
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'human_review',
                'status': 'pending_review' if claude_result['success'] else 'failed',
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
            'image_id': image_id,
            'filename': filename,
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'processing_mode': 'human_review',
            'status': 'pending_review' if claude_result['success'] else 'failed',
            'claude_result': claude_result,
            's3_pending_key': pending_key,
            's3_key': s3_key
        })
        
    except Exception as e:
        # 如果有 image_id，更新狀態為失敗
        if 'image_id' in locals():
            update_image_processing_status(image_id, 'failed')
        return jsonify({'error': f'人工審核處理失敗: {str(e)}'}), 500

@app.route('/submit_human_review', methods=['POST'])
def submit_human_review():
    """提交人工審核後的結果到DynamoDB"""
    try:
        data = request.json
        session_id = data.get('session_id')
        image_id = data.get('image_id')  # 從前端傳入
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
        
        # 如果有 image_id，更新圖片處理狀態
        if image_id and db_result['success']:
            update_image_processing_status(image_id, 'completed', db_result['record_id'])
        elif image_id:
            update_image_processing_status(image_id, 'failed')
        
        # 更新 S3 中的狀態
        final_key = f"human_reviewed/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=final_key,
            Body=json.dumps({
                'session_id': session_id,
                'image_id': image_id,
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
            'image_id': image_id,
            'status': 'completed',
            'dynamodb_result': db_result
        })
        
    except Exception as e:
        # 如果有 image_id，更新狀態為失敗
        if 'image_id' in locals():
            update_image_processing_status(image_id, 'failed')
        return jsonify({'error': f'提交審核結果失敗: {str(e)}'}), 500

@app.route('/images')
def images_list():
    """圖片管理頁面"""
    return render_template('images_list.html')

@app.route('/api/images')
def api_get_images():
    """API: 獲取圖片列表"""
    limit = request.args.get('limit', 50, type=int)
    result = get_uploaded_images(limit)
    return jsonify(result)

@app.route('/api/images/<image_id>')
def api_get_image_details(image_id):
    """API: 獲取圖片詳細信息包括OCR結果"""
    try:
        # 獲取圖片信息
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            return jsonify({'error': '圖片不存在'}), 404
        
        image_item = response['Item']
        
        if image_item.get('record_type') != 'image_metadata':
            return jsonify({'error': '無效的圖片記錄'}), 400
        
        # 生成S3預簽名URL用於圖片預覽
        try:
            image_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': S3_BUCKET, 'Key': image_item['s3_key']},
                ExpiresIn=3600  # 1小時過期
            )
        except Exception as e:
            print(f"❌ Failed to generate presigned URL: {str(e)}")
            image_url = None
        
        result = {
            'success': True,
            'image_id': image_id,
            'filename': image_item['filename'],
            'processing_status': image_item.get('processing_status', 'unknown'),
            'upload_time': image_item.get('upload_time'),
            'file_size': image_item.get('file_size'),
            'content_type': image_item.get('content_type'),
            'image_url': image_url
        }
        
        # 如果有OCR結果，獲取OCR結果
        if 'ocr_result_id' in image_item:
            ocr_result_id = image_item['ocr_result_id']
            ocr_response = dynamodb_table.get_item(Key={'id': ocr_result_id})
            
            if 'Item' in ocr_response:
                ocr_item = ocr_response['Item']
                result['ocr_result'] = {
                    'id': ocr_result_id,
                    'data': ocr_item.get('data', {}),
                    'processing_mode': ocr_item.get('processing_mode'),
                    'confidence_score': float(ocr_item.get('confidence_score', 0)) if ocr_item.get('confidence_score') else None,
                    'human_reviewed': ocr_item.get('human_reviewed', False),
                    'created_at': ocr_item.get('created_at'),
                    'updated_at': ocr_item.get('updated_at')
                }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ API error: {str(e)}")
        return jsonify({'error': f'獲取圖片詳情失敗: {str(e)}'}), 500

@app.route('/api/images/<image_id>/reprocess', methods=['POST'])
def api_reprocess_image(image_id):
    """API: 重新處理指定圖片"""
    try:
        # 獲取圖片信息
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            return jsonify({'error': '圖片不存在'}), 404
        
        image_item = response['Item']
        if image_item.get('record_type') != 'image_metadata':
            return jsonify({'error': '無效的圖片記錄'}), 400
        
        # 從 S3 下載圖片
        s3_response = s3_client.get_object(Bucket=S3_BUCKET, Key=image_item['s3_key'])
        file_data = s3_response['Body'].read()
        
        # 更新處理狀態
        update_image_processing_status(image_id, 'processing')
        
        # 執行處理
        processing_mode = request.json.get('processing_mode', 'automatic')
        
        if processing_mode == 'automatic':
            # 執行自動處理
            voting_results = run_enhanced_voting_system(file_data)
            
            if voting_results and 'voting_result' in voting_results and 'final_result' in voting_results['voting_result']:
                vote_details = voting_results['voting_result'].get('vote_details', {})
                avg_confidence = sum(detail['confidence'] for detail in vote_details.values()) / len(vote_details) if vote_details else 0
                
                final_result = voting_results['voting_result']['final_result']
                db_result = save_to_dynamodb(
                    data=final_result,
                    processing_mode='automatic_reprocess',
                    confidence_score=avg_confidence,
                    human_reviewed=False
                )
                
                if db_result['success']:
                    update_image_processing_status(image_id, 'completed', db_result['record_id'])
                    return jsonify({
                        'success': True,
                        'message': '重新處理完成',
                        'ocr_result_id': db_result['record_id']
                    })
                else:
                    update_image_processing_status(image_id, 'failed')
                    return jsonify({'error': f'OCR結果保存失敗: {db_result["error"]}'}), 500
            else:
                update_image_processing_status(image_id, 'failed')
                return jsonify({'error': '處理失敗：無效的結果結構'}), 500
        else:
            # 人工審核模式
            claude_result = process_with_claude_latest(file_data, for_human_review=True)
            if claude_result['success']:
                update_image_processing_status(image_id, 'pending_review')
                return jsonify({
                    'success': True,
                    'message': '準備人工審核',
                    'claude_result': claude_result,
                    'image_id': image_id
                })
            else:
                update_image_processing_status(image_id, 'failed')
                return jsonify({'error': f'處理失敗: {claude_result["error"]}'}), 500
        
    except Exception as e:
        if 'image_id' in locals():
            update_image_processing_status(image_id, 'failed')
        return jsonify({'error': f'重新處理失敗: {str(e)}'}), 500

@app.route('/api/images/<image_id>/review', methods=['GET'])
def api_get_image_for_review(image_id):
    """API: 獲取待審核圖片的詳細信息用於人工審核"""
    try:
        print(f"🔍 Getting image for review: {image_id}")
        
        # 獲取圖片信息
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            print(f"❌ Image not found: {image_id}")
            return jsonify({'error': '圖片不存在'}), 404
        
        image_item = response['Item']
        print(f"📋 Image item: {image_item.get('filename')} - {image_item.get('processing_status')}")
        
        if image_item.get('record_type') != 'image_metadata':
            return jsonify({'error': '無效的圖片記錄'}), 400
        
        if image_item.get('processing_status') != 'pending_review':
            return jsonify({'error': f'圖片狀態為 {image_item.get("processing_status")}，不在待審核狀態'}), 400
        
        # 從 S3 獲取待審核的結果
        session_id = image_item.get('session_id')
        if not session_id:
            return jsonify({'error': '缺少會話ID'}), 400
        
        claude_result = None
        
        # 嘗試從 S3 獲取待審核結果 (嘗試多個可能的日期)
        for days_back in range(7):  # 嘗試過去7天
            try:
                from datetime import timedelta
                check_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
                pending_key = f"pending_review/{check_date}/{session_id}.json"
                print(f"🔍 Trying pending key: {pending_key}")
                
                s3_response = s3_client.get_object(Bucket=S3_BUCKET, Key=pending_key)
                pending_data = json.loads(s3_response['Body'].read().decode('utf-8'))
                claude_result = pending_data.get('claude_result', {})
                print(f"✅ Found pending data from {check_date}")
                break
            except Exception as e:
                print(f"⚠️ No pending data for {check_date}: {str(e)}")
                continue
        
        # 如果找不到待審核結果，重新處理
        if not claude_result or not claude_result.get('success'):
            print("🔄 No pending data found, reprocessing...")
            try:
                s3_response = s3_client.get_object(Bucket=S3_BUCKET, Key=image_item['s3_key'])
                file_data = s3_response['Body'].read()
                claude_result = process_with_claude_latest(file_data, for_human_review=True)
                print(f"✅ Reprocessed with result: {claude_result.get('success')}")
            except Exception as e:
                print(f"❌ Reprocessing failed: {str(e)}")
                return jsonify({'error': f'無法重新處理圖片: {str(e)}'}), 500
        
        if not claude_result.get('success'):
            return jsonify({'error': '無法獲取處理結果'}), 500
        
        # 從 S3 獲取原始圖片
        try:
            s3_response = s3_client.get_object(Bucket=S3_BUCKET, Key=image_item['s3_key'])
            file_data = s3_response['Body'].read()
        except Exception as e:
            print(f"❌ Failed to get image from S3: {str(e)}")
            return jsonify({'error': f'無法獲取原始圖片: {str(e)}'}), 500
        
        # 準備圖片顯示
        file_base64 = base64.b64encode(file_data).decode('utf-8')
        file_type = image_item['content_type'].split('/')[-1]
        
        print(f"✅ Successfully prepared review data for {image_item['filename']}")
        
        return jsonify({
            'success': True,
            'image_id': image_id,
            'session_id': session_id,
            'filename': image_item['filename'],
            'image_data': f"data:image/{file_type};base64,{file_base64}",
            'processing_mode': 'human_review',
            'status': 'pending_review',
            'claude_result': claude_result
        })
        
    except Exception as e:
        print(f"❌ API error: {str(e)}")
        return jsonify({'error': f'獲取審核資料失敗: {str(e)}'}), 500

@app.route('/edit/<image_id>')
def edit_ocr(image_id):
    """OCR結果編輯頁面"""
    return render_template('edit_ocr.html', image_id=image_id)

@app.route('/enhanced_voting_ocr')
def enhanced_voting_ocr():
    """Enhanced voting OCR page with optional edit functionality"""
    edit_image_id = request.args.get('edit_image_id')
    if edit_image_id:
        # Edit mode - load existing OCR result for editing
        return render_template('enhanced_voting_ocr.html', review_mode=True, image_id=edit_image_id, edit_mode=True)
    else:
        # Normal mode - new upload
        return render_template('enhanced_voting_ocr.html', review_mode=False, image_id=None, edit_mode=False)

@app.route('/review/<image_id>')
def review_image(image_id):
    """人工審核頁面"""
    return render_template('enhanced_voting_ocr.html', review_mode=True, image_id=image_id, edit_mode=False)

@app.route('/api/images/<image_id>/ocr-result', methods=['GET'])
def api_get_image_ocr_result(image_id):
    """API: 獲取圖片的OCR結果詳情"""
    try:
        print(f"🔍 Getting OCR result for image: {image_id}")
        
        # 獲取圖片信息
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            return jsonify({'error': '圖片不存在'}), 404
        
        image_item = response['Item']
        if image_item.get('record_type') != 'image_metadata':
            return jsonify({'error': '無效的圖片記錄'}), 400
        
        ocr_result_id = image_item.get('ocr_result_id')
        if not ocr_result_id:
            return jsonify({'error': '此圖片尚未處理或處理失敗'}), 404
        
        # 獲取OCR結果
        ocr_response = dynamodb_table.get_item(Key={'id': ocr_result_id})
        if 'Item' not in ocr_response:
            return jsonify({'error': 'OCR結果不存在'}), 404
        
        ocr_item = ocr_response['Item']
        
        # 生成預簽名URL用於圖片預覽
        image_url = None
        if 's3_key' in image_item:
            try:
                image_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET, 'Key': image_item['s3_key']},
                    ExpiresIn=3600  # 1小時有效期
                )
            except Exception as e:
                print(f"⚠️ Failed to generate presigned URL: {str(e)}")
                image_url = None
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'image_info': {
                'id': image_item['id'],
                'filename': image_item['filename'],
                'processing_status': image_item['processing_status'],
                'created_at': image_item['created_at'],
                'updated_at': image_item['updated_at']
            },
            'ocr_result': {
                'id': ocr_item['id'],
                'processing_mode': ocr_item['processing_mode'],
                'human_reviewed': ocr_item.get('human_reviewed', False),
                'confidence_score': float(ocr_item.get('confidence_score', 0)) if ocr_item.get('confidence_score') else None,
                'data': ocr_item['data'],
                'created_at': ocr_item['created_at']
            }
        })
        
    except Exception as e:
        print(f"❌ OCR result API error: {str(e)}")
        return jsonify({'error': f'獲取OCR結果失敗: {str(e)}'}), 500

@app.route('/api/images/<image_id>/update-ocr', methods=['POST'])
def api_update_ocr_result(image_id):
    """API: 更新OCR結果"""
    try:
        print(f"🔄 Updating OCR result for image: {image_id}")
        
        # 獲取請求資料
        data = request.get_json()
        if not data:
            return jsonify({'error': '無效的請求資料'}), 400
        
        # 獲取現有的OCR結果
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            return jsonify({'error': '找不到指定的圖片'}), 404
        
        image_item = response['Item']
        
        # 檢查是否有OCR結果
        if 'ocr_result_id' not in image_item:
            return jsonify({'error': '此圖片尚未有OCR結果'}), 400
        
        ocr_result_id = image_item['ocr_result_id']
        
        # 獲取現有的OCR結果
        ocr_response = dynamodb_table.get_item(Key={'id': ocr_result_id})
        if 'Item' not in ocr_response:
            return jsonify({'error': '找不到OCR結果'}), 404
        
        ocr_item = ocr_response['Item']
        
        # 正規化日期格式
        normalized_data = normalize_dates_in_data(data)
        print(f"📅 更新OCR結果時日期正規化完成: {json.dumps(normalized_data, indent=2, ensure_ascii=False)}")
        
        # 轉換浮點數為Decimal
        updated_data = convert_floats_to_decimal(normalized_data)
        
        # 更新OCR結果記錄
        update_expression = "SET #data = :data, updated_at = :updated_at, human_reviewed = :human_reviewed"
        expression_attribute_names = {
            '#data': 'data'
        }
        expression_attribute_values = {
            ':data': updated_data,
            ':updated_at': datetime.utcnow().isoformat(),
            ':human_reviewed': True
        }
        
        dynamodb_table.update_item(
            Key={'id': ocr_result_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
        
        # 更新圖片狀態為已完成
        dynamodb_table.update_item(
            Key={'id': image_id},
            UpdateExpression="SET processing_status = :status, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':status': 'completed',
                ':updated_at': datetime.utcnow().isoformat()
            }
        )
        
        print(f"✅ OCR result updated successfully for image: {image_id}")
        
        return jsonify({
            'success': True,
            'message': 'OCR結果更新成功',
            'ocr_result_id': ocr_result_id
        })
        
    except Exception as e:
        print(f"❌ Update OCR result error: {str(e)}")
        return jsonify({'error': f'更新OCR結果失敗: {str(e)}'}), 500

@app.route('/api/images/<image_id>/delete', methods=['DELETE'])
def api_delete_image(image_id):
    """API: 刪除圖片"""
    try:
        print(f"🗑️ Deleting image: {image_id}")
        
        # 獲取圖片信息
        response = dynamodb_table.get_item(Key={'id': image_id})
        if 'Item' not in response:
            return jsonify({'error': '圖片不存在'}), 404
        
        image_item = response['Item']
        if image_item.get('record_type') != 'image_metadata':
            return jsonify({'error': '無效的圖片記錄'}), 400
        
        print(f"📋 Deleting: {image_item['filename']} from {image_item['s3_key']}")
        
        # 從 S3 刪除圖片
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=image_item['s3_key'])
            print(f"✅ Deleted from S3: {image_item['s3_key']}")
        except Exception as s3_error:
            print(f"⚠️ S3 刪除警告: {str(s3_error)}")
        
        # 嘗試刪除相關的 S3 文件 (pending_review, results 等)
        session_id = image_item.get('session_id')
        if session_id:
            # 刪除可能的待審核文件
            for days_back in range(7):
                try:
                    from datetime import timedelta
                    check_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
                    pending_key = f"pending_review/{check_date}/{session_id}.json"
                    s3_client.delete_object(Bucket=S3_BUCKET, Key=pending_key)
                    print(f"✅ Deleted pending file: {pending_key}")
                except:
                    pass
            
            # 刪除可能的結果文件
            try:
                results_key = f"automatic_results/{datetime.now().strftime('%Y/%m/%d')}/{session_id}.json"
                s3_client.delete_object(Bucket=S3_BUCKET, Key=results_key)
                print(f"✅ Deleted results file: {results_key}")
            except:
                pass
        
        # 從 DynamoDB 刪除記錄
        dynamodb_table.delete_item(Key={'id': image_id})
        print(f"✅ Deleted from DynamoDB: {image_id}")
        
        # 如果有關聯的 OCR 結果，也嘗試刪除
        ocr_result_id = image_item.get('ocr_result_id')
        if ocr_result_id:
            try:
                dynamodb_table.delete_item(Key={'id': ocr_result_id})
                print(f"✅ Deleted OCR result: {ocr_result_id}")
            except Exception as ocr_error:
                print(f"⚠️ OCR result deletion warning: {str(ocr_error)}")
        
        return jsonify({'success': True, 'message': '圖片已刪除'})
        
    except Exception as e:
        print(f"❌ Delete error: {str(e)}")
        return jsonify({'error': f'刪除失敗: {str(e)}'}), 500
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
    
    # Check if running in production (App Runner sets PORT env var)
    import os
    debug_mode = os.getenv('FLASK_ENV', 'development') == 'development'
    port = int(os.getenv('PORT', 5006))
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
