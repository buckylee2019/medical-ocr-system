# Medical Document OCR Web Application

A web application that uses Amazon Nova for OCR processing of medical documents, allows human review and editing, and saves the final data to S3.

## Features

- **Document Upload**: Drag & drop or click to upload medical documents (PNG, JPG, JPEG, PDF, TIFF)
- **AI-Powered OCR**: Uses Amazon Nova for intelligent text extraction from medical handwriting
- **Human Review**: Interactive form for reviewing and editing extracted information
- **S3 Storage**: Automatically saves processed data to Amazon S3
- **Responsive UI**: Modern Bootstrap-based interface that works on desktop and mobile

## Architecture

```
User Upload → Amazon Nova OCR → Review Form → Amazon S3
```

## Prerequisites

- AWS Account with access to:
  - Amazon Bedrock (Nova models)
  - Amazon S3
- Python 3.8+
- AWS CLI configured or environment variables set

## Quick Start

1. **Clone and Setup**
   ```bash
   cd /Users/buckylee/Documents/playground/rpa_ocr
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and settings
   ```

3. **Run Setup Script**
   ```bash
   python setup.py
   ```

4. **Start the Application**
   ```bash
   python app.py
   ```

5. **Open Browser**
   Navigate to `http://localhost:5000`

## Configuration

### Environment Variables (.env)

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
S3_BUCKET=medical-ocr-documents

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# Optional: Specific Nova model
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

### AWS Permissions

Your AWS user/role needs the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

## Usage

1. **Upload Document**: Drag and drop or click to select a medical document
2. **AI Processing**: Amazon Nova automatically extracts text and structures it
3. **Review & Edit**: Use the interactive form to review and modify extracted data
4. **Save**: Click "Save to S3" to store the final processed data

## Extracted Data Structure

The application extracts and structures the following medical information:

```json
{
    "patient_name": "John Doe",
    "date_of_birth": "1980-01-15",
    "date_of_service": "2024-01-20",
    "provider_name": "Dr. Smith",
    "diagnosis": "Hypertension",
    "medications": ["Lisinopril", "Metformin"],
    "dosage": "10mg daily",
    "instructions": "Take with food",
    "notes": "Follow up in 3 months"
}
```

## API Endpoints

- `GET /` - Main upload interface
- `POST /upload` - Process document upload
- `POST /save` - Save reviewed data to S3
- `GET /health` - Health check endpoint

## File Structure

```
rpa_ocr/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html        # Web interface
├── requirements.txt      # Python dependencies
├── setup.py             # AWS setup script
├── .env.example         # Environment template
├── README.md           # This file
└── todo.md            # Project roadmap
```

## Customization

### Adding New Document Types

Modify the `process_document_with_nova()` function in `app.py` to handle different document types:

```python
if document_type == "prescription":
    prompt = "Extract prescription information..."
elif document_type == "lab_report":
    prompt = "Extract lab results..."
```

### Changing Form Fields

Update both the HTML form in `templates/index.html` and the processing logic in `app.py` to match your specific needs.

### S3 Storage Structure

Files are saved to S3 with the following structure:
```
s3://your-bucket/processed/YYYY/MM/DD/session-id.json
```

## Troubleshooting

### Common Issues

1. **Bedrock Access Denied**
   - Ensure your AWS region supports Amazon Nova
   - Check IAM permissions for Bedrock access

2. **S3 Upload Fails**
   - Verify S3 bucket exists and is accessible
   - Check IAM permissions for S3 operations

3. **Large File Upload**
   - Current limit is 16MB
   - Adjust `MAX_CONTENT_LENGTH` in app.py if needed

### Debugging

Enable debug mode by setting `FLASK_ENV=development` in your `.env` file.

## Security Considerations

- **HIPAA Compliance**: Ensure your AWS setup meets HIPAA requirements
- **Data Encryption**: Enable S3 encryption at rest
- **Access Control**: Use IAM roles with minimal required permissions
- **Network Security**: Consider VPC deployment for production

## Production Deployment

For production deployment, consider:

1. **Use WSGI Server**: Deploy with Gunicorn or uWSGI
2. **Load Balancer**: Use ALB for high availability
3. **Database**: Add persistent storage for session management
4. **Monitoring**: Implement CloudWatch logging and monitoring
5. **Security**: Enable HTTPS and proper authentication

## Cost Optimization

- **Nova Model Selection**: Choose between nova-micro and nova-lite based on accuracy needs
- **S3 Storage Class**: Use appropriate storage class for your retention requirements
- **Batch Processing**: Consider batch processing for high-volume scenarios

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review AWS documentation for Bedrock and S3
3. Check application logs for detailed error messages

## License

This project is provided as-is for educational and development purposes.
