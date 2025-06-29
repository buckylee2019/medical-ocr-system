#!/usr/bin/env python3
"""
Test script to check if models are extracting all fields correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_medical_extraction_prompt, parse_json_response
import json

def test_prompt_structure():
    """Test the medical extraction prompt structure"""
    print("🔍 Testing Medical Extraction Prompt Structure")
    print("=" * 60)
    
    prompt = get_medical_extraction_prompt()
    print("📋 Prompt Content:")
    print(prompt)
    print("\n" + "=" * 60)
    
    # Extract expected JSON structure from prompt
    import re
    json_match = re.search(r'\{.*?\}', prompt, re.DOTALL)
    if json_match:
        try:
            expected_structure = json.loads(json_match.group(0))
            print("✅ Expected JSON Structure:")
            print(json.dumps(expected_structure, indent=2, ensure_ascii=False))
            
            print("\n📊 Expected Fields Count:")
            for section, fields in expected_structure.items():
                if isinstance(fields, dict):
                    print(f"  - {section}: {len(fields)} fields")
                    for field in fields.keys():
                        print(f"    • {field}")
                else:
                    print(f"  - {section}: {type(fields)}")
                    
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
    else:
        print("❌ No JSON structure found in prompt")

def test_json_parsing():
    """Test JSON response parsing with sample data"""
    print("\n🧪 Testing JSON Response Parsing")
    print("=" * 60)
    
    # Sample JSON response (what we expect from Claude)
    sample_response = """{
        "certificate_info": {
            "certificate_no": "TEST-001",
            "certificate_date": "2024-01-01"
        },
        "patient_info": {
            "name": "測試病患",
            "sex": "男",
            "date_of_birth": "1990-01-01",
            "nationality": "中華民國",
            "passport_no_or_id": "A123456789",
            "medical_history_no": "MH001",
            "address": "台北市信義區"
        },
        "examination_info": {
            "date_of_examination": "2024-01-01",
            "department": "內科"
        },
        "medical_content": {
            "diagnosis": "感冒",
            "doctors_comment": "多休息多喝水"
        },
        "hospital_info": {
            "hospital_name_chinese": "測試醫院",
            "hospital_name_english": "Test Hospital",
            "superintendent": "院長姓名",
            "attending_physician": "主治醫師姓名"
        },
        "additional_info": {
            "stamp_or_seal": "醫院印章",
            "other_notes": "其他備註"
        }
    }"""
    
    try:
        parsed_data = parse_json_response(sample_response)
        print("✅ JSON Parsing Successful:")
        print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
        
        print("\n📊 Parsed Fields Count:")
        for section, fields in parsed_data.items():
            if isinstance(fields, dict):
                non_empty = sum(1 for v in fields.values() if v)
                print(f"  - {section}: {len(fields)} fields, {non_empty} non-empty")
            else:
                print(f"  - {section}: {type(fields)}")
                
    except Exception as e:
        print(f"❌ JSON parsing failed: {e}")

def test_markdown_wrapped_json():
    """Test parsing JSON wrapped in markdown"""
    print("\n🧪 Testing Markdown-Wrapped JSON Parsing")
    print("=" * 60)
    
    markdown_response = """Here is the extracted information:

```json
{
    "certificate_info": {
        "certificate_no": "MD-2024-001",
        "certificate_date": "2024-01-15"
    },
    "patient_info": {
        "name": "王小明",
        "sex": "男"
    }
}
```

This is the medical information extracted from the document."""
    
    try:
        parsed_data = parse_json_response(markdown_response)
        print("✅ Markdown JSON Parsing Successful:")
        print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Markdown JSON parsing failed: {e}")

def check_field_completeness():
    """Check if all expected fields are present"""
    print("\n🔍 Checking Field Completeness")
    print("=" * 60)
    
    expected_sections = [
        'certificate_info',
        'patient_info', 
        'examination_info',
        'medical_content',
        'hospital_info',
        'additional_info'
    ]
    
    expected_fields = {
        'certificate_info': ['certificate_no', 'certificate_date'],
        'patient_info': ['name', 'sex', 'date_of_birth', 'nationality', 'passport_no_or_id', 'medical_history_no', 'address'],
        'examination_info': ['date_of_examination', 'department'],
        'medical_content': ['diagnosis', 'doctors_comment'],
        'hospital_info': ['hospital_name_chinese', 'hospital_name_english', 'superintendent', 'attending_physician'],
        'additional_info': ['stamp_or_seal', 'other_notes']
    }
    
    print("📋 Expected Structure:")
    total_fields = 0
    for section, fields in expected_fields.items():
        print(f"  - {section}: {len(fields)} fields")
        total_fields += len(fields)
        for field in fields:
            print(f"    • {field}")
    
    print(f"\n📊 Total Expected Fields: {total_fields}")
    
    return expected_fields

if __name__ == "__main__":
    print("🚀 Medical OCR Field Extraction Test")
    print("=" * 80)
    
    test_prompt_structure()
    test_json_parsing()
    test_markdown_wrapped_json()
    check_field_completeness()
    
    print("\n💡 Next Steps:")
    print("1. Run the application and check console logs for field extraction")
    print("2. Compare actual extraction with expected structure above")
    print("3. Check if models are returning empty values for certain fields")
    print("4. Verify that voting system is properly aggregating all fields")
