import json
import re
from datetime import datetime
import boto3

def lambda_handler(event, context):
    """
    Lambda function to validate extracted medical data
    This mimics RPA data validation rules
    """
    
    extracted_data = event['extracted_data']
    confidence_scores = event['confidence_scores']
    session_id = event['session_id']
    
    try:
        # Perform comprehensive validation
        validation_results = validate_medical_data(extracted_data)
        
        # Calculate final confidence score
        final_confidence = calculate_final_confidence(confidence_scores, validation_results)
        
        # Determine next action
        next_action = determine_next_action(final_confidence, validation_results)
        
        return {
            'statusCode': 200,
            'confidence_score': final_confidence,
            'validation_results': validation_results,
            'next_action': next_action,
            'session_id': session_id,
            'requires_human_review': final_confidence < 0.8,
            'validation_passed': validation_results['overall_valid']
        }
        
    except Exception as e:
        print(f"Error validating data: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'session_id': session_id,
            'confidence_score': 0.0
        }

def validate_medical_data(data):
    """Comprehensive medical data validation"""
    
    validation_results = {
        'overall_valid': True,
        'field_validations': {},
        'warnings': [],
        'errors': []
    }
    
    # Validate patient name
    if 'patient_name' in data:
        name_validation = validate_patient_name(data['patient_name'])
        validation_results['field_validations']['patient_name'] = name_validation
        if not name_validation['valid']:
            validation_results['overall_valid'] = False
            validation_results['errors'].append(f"Invalid patient name: {name_validation['reason']}")
    
    # Validate dates
    for date_field in ['date_of_birth', 'issue_date']:
        if date_field in data and data[date_field]:
            date_validation = validate_date(data[date_field], date_field)
            validation_results['field_validations'][date_field] = date_validation
            if not date_validation['valid']:
                validation_results['warnings'].append(f"Date issue in {date_field}: {date_validation['reason']}")
    
    # Validate hospital name
    if 'hospital_name' in data and data['hospital_name']:
        hospital_validation = validate_hospital_name(data['hospital_name'])
        validation_results['field_validations']['hospital_name'] = hospital_validation
        if not hospital_validation['valid']:
            validation_results['warnings'].append(f"Hospital name issue: {hospital_validation['reason']}")
    
    # Validate medications
    if 'medications' in data:
        med_validation = validate_medications(data['medications'])
        validation_results['field_validations']['medications'] = med_validation
        if med_validation['warnings']:
            validation_results['warnings'].extend(med_validation['warnings'])
    
    # Validate dosage format
    if 'dosage' in data and data['dosage']:
        dosage_validation = validate_dosage(data['dosage'])
        validation_results['field_validations']['dosage'] = dosage_validation
        if not dosage_validation['valid']:
            validation_results['warnings'].append(f"Dosage format issue: {dosage_validation['reason']}")
    
    # Check for required fields
    required_fields = ['patient_name', 'issue_date']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        validation_results['errors'].append(f"Missing required fields: {', '.join(missing_fields)}")
        validation_results['overall_valid'] = False
    
    return validation_results

def validate_patient_name(name):
    """Validate patient name format"""
    if not name or len(name.strip()) < 2:
        return {'valid': False, 'reason': 'Name too short or empty'}
    
    # Check for reasonable name pattern
    if not re.match(r'^[A-Za-z\s\-\.\']+$', name):
        return {'valid': False, 'reason': 'Name contains invalid characters'}
    
    # Check for common OCR errors
    if any(char in name for char in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']):
        return {'valid': False, 'reason': 'Name contains numbers (possible OCR error)'}
    
    return {'valid': True, 'confidence': 0.9}

def validate_date(date_str, field_name):
    """Validate date format and reasonableness"""
    try:
        # Try to parse the date
        if '-' in date_str:
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
        elif '/' in date_str:
            parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
        else:
            return {'valid': False, 'reason': 'Unrecognized date format'}
        
        # Check date reasonableness
        current_date = datetime.now()
        
        if field_name == 'date_of_birth':
            # Birth date should be in the past and reasonable
            if parsed_date > current_date:
                return {'valid': False, 'reason': 'Birth date is in the future'}
            if (current_date - parsed_date).days > 36500:  # ~100 years
                return {'valid': False, 'reason': 'Birth date is too old'}
        
        elif field_name == 'issue_date':
            # Issue date should be reasonable (not too far in future/past)
            days_diff = abs((current_date - parsed_date).days)
            if days_diff > 365:  # More than a year
                return {'valid': True, 'reason': 'Issue date is more than a year old', 'warning': True}
        
        return {'valid': True, 'parsed_date': parsed_date.isoformat()}
        
    except ValueError as e:
        return {'valid': False, 'reason': f'Date parsing error: {str(e)}'}

def validate_medications(medications):
    """Validate medication names and format"""
    validation_result = {
        'valid': True,
        'warnings': [],
        'validated_medications': []
    }
    
    if not medications:
        return validation_result
    
    # Handle both string and list formats
    if isinstance(medications, str):
        med_list = [med.strip() for med in medications.split(',')]
    elif isinstance(medications, list):
        med_list = medications
    else:
        validation_result['warnings'].append('Medications in unexpected format')
        return validation_result
    
    # Common medication name patterns
    med_pattern = re.compile(r'^[A-Za-z][A-Za-z0-9\s\-\.]*$')
    
    for med in med_list:
        if not med or len(med.strip()) < 2:
            validation_result['warnings'].append(f'Very short medication name: "{med}"')
            continue
            
        if not med_pattern.match(med.strip()):
            validation_result['warnings'].append(f'Unusual medication name format: "{med}"')
        
        validation_result['validated_medications'].append(med.strip())
    
    return validation_result

def validate_dosage(dosage):
    """Validate dosage format"""
    # Common dosage patterns
    dosage_patterns = [
        r'\d+\s*mg',  # 10 mg
        r'\d+\s*mcg', # 50 mcg
        r'\d+\s*ml',  # 5 ml
        r'\d+\s*units', # 10 units
        r'\d+\s*times?\s*(daily|per\s*day|a\s*day)', # 2 times daily
        r'once\s*(daily|per\s*day|a\s*day)', # once daily
        r'twice\s*(daily|per\s*day|a\s*day)', # twice daily
    ]
    
    dosage_lower = dosage.lower()
    
    for pattern in dosage_patterns:
        if re.search(pattern, dosage_lower):
            return {'valid': True, 'confidence': 0.8}
    
    # If no pattern matches, it might still be valid but unusual
    return {'valid': True, 'confidence': 0.5, 'reason': 'Unusual dosage format'}

def calculate_final_confidence(confidence_scores, validation_results):
    """Calculate final confidence score combining OCR and validation results"""
    
    base_confidence = confidence_scores.get('overall_confidence', 0.5)
    
    # Adjust based on validation results
    if validation_results['overall_valid']:
        validation_boost = 0.2
    else:
        validation_boost = -0.3
    
    # Adjust based on warnings
    warning_penalty = len(validation_results['warnings']) * 0.05
    error_penalty = len(validation_results['errors']) * 0.15
    
    final_confidence = base_confidence + validation_boost - warning_penalty - error_penalty
    
    # Ensure confidence is between 0 and 1
    return max(0.0, min(1.0, final_confidence))

def validate_hospital_name(hospital_name):
    """Validate hospital name format"""
    if not hospital_name or len(hospital_name.strip()) < 2:
        return {'valid': False, 'reason': 'Hospital name too short or empty'}
    
    # Check for reasonable hospital name pattern
    if len(hospital_name) > 200:
        return {'valid': False, 'reason': 'Hospital name too long'}
    
    # Check for common OCR errors (too many numbers)
    digit_count = sum(1 for char in hospital_name if char.isdigit())
    if digit_count > len(hospital_name) * 0.3:  # More than 30% digits
        return {'valid': False, 'reason': 'Hospital name contains too many numbers (possible OCR error)'}
    
    return {'valid': True, 'confidence': 0.8}

def determine_next_action(confidence_score, validation_results):
    """Determine the next action based on confidence and validation"""
    
    if not validation_results['overall_valid']:
        return 'manual_processing'
    elif confidence_score >= 0.8:
        return 'auto_approve'
    elif confidence_score >= 0.5:
        return 'human_review'
    else:
        return 'manual_processing'
