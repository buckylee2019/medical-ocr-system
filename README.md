# 🏥 Medical OCR System with AWS Bedrock

A production-ready web application that uses **Amazon Bedrock Claude AI models** for intelligent OCR processing of medical documents, featuring human-in-the-loop review and comprehensive medical document management.

## ✨ Features

### 🤖 **AI-Powered OCR Processing**
- **Multi-Model Voting**: Claude 3.5 Sonnet, Claude 3 Haiku, Claude 3.7 Sonnet
- **Automatic Processing**: Full automation with confidence scoring
- **Human Review**: Manual review and correction workflow
- **Medical Document Focus**: Optimized for medical certificates and forms

### 📋 **Medical Document Management**
- **Complete Image Management**: Upload, process, view, and delete medical images
- **Structured Data Display**: Organized medical information extraction
- **Status Tracking**: Real-time processing status monitoring
- **Medical Content Sections**:
  - 🩺 **Diagnosis & Treatment**: Medical diagnosis and doctor recommendations
  - 👤 **Patient Information**: Complete patient details
  - 📅 **Examination Info**: Examination dates and departments
  - 🏥 **Hospital Information**: Medical facility and physician details
  - 📋 **Certificate Info**: Medical certificate numbers and dates

### 🔄 **Processing Workflows**
- **Automatic Path**: AI models vote and auto-save to database
- **Human Review Path**: Manual verification and editing
- **Pending Review Management**: Queue system for human oversight
- **Confidence Scoring**: AI confidence metrics for quality assurance

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Interface │───▶│   Flask App      │───▶│   AWS Bedrock   │
│   (Bootstrap)   │    │   (Python)       │    │   (Claude AI)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   DynamoDB       │    │   S3 Bucket     │
                       │   (Data Store)   │    │   (Images)      │
                       └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### **Prerequisites**
- AWS Account with access to:
  - ✅ Amazon Bedrock (Claude models)
  - ✅ Amazon DynamoDB
  - ✅ Amazon S3
- Python 3.11+
- AWS CLI configured

### **1. Setup Environment**
```bash
# Clone repository
git clone https://github.com/buckylee2019/medical-ocr-system.git
cd medical-ocr-system

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your AWS settings
```

### **2. Create AWS Resources**
```bash
# Create DynamoDB table
python create_dynamodb_table.py
```

### **3. Run Application**
```bash
# Start the Flask application
python app.py

# Access the application
# http://localhost:5006
```

## 🌐 Web Interface

### **Main Processing Interface** (`/`)
- Choose processing path (Automatic vs Human Review)
- Upload medical document images
- Real-time processing status
- Results display with confidence scores

### **Image Management** (`/images`)
- View all uploaded medical images
- Click images to see detailed medical content
- Manage processing status
- Delete unwanted images

### **Human Review Interface** (`/review/<id>`)
- Review AI-extracted medical information
- Edit and correct any inaccuracies
- Submit final reviewed data
- Cancel and return to queue

## 📊 API Endpoints

- `GET /health` - Health check for monitoring
- `GET /api/images` - List all medical images
- `GET /api/images/<id>/ocr-result` - Get detailed medical content
- `DELETE /api/images/<id>/delete` - Delete image and data
- `POST /process` - Process uploaded medical document
- `POST /submit_review` - Submit human review results

## 🔧 Configuration

### **Environment Variables** (`.env`)
```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-west-2
AWS_PROFILE=your-profile-name

# DynamoDB
DYNAMODB_TABLE_NAME=medical-ocr-data

# S3 Storage
S3_BUCKET=your-medical-ocr-bucket

# Application
FLASK_ENV=development
FLASK_DEBUG=True
```

### **AWS Services Setup**
- **Bedrock**: Enable Claude 3.5 Sonnet, Claude 3 Haiku, Claude 3.7 Sonnet models
- **DynamoDB**: Table created automatically with `create_dynamodb_table.py`
- **S3**: Bucket for image storage with proper CORS configuration
- **IAM**: Appropriate permissions for Bedrock, DynamoDB, and S3 access

## 🚀 AWS Deployment

### **Deploy to AWS App Runner** (Recommended)
```bash
# 1. Set up AWS resources
cd deploy
./quick_deploy.sh

# 2. Push to GitHub (already done)
# 3. Create App Runner service in AWS Console
# 4. Connect GitHub repository
# 5. Deploy automatically
```

**Estimated Cost**: ~$30-40/month for production use

For detailed deployment instructions, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

## 🧪 Testing

```bash
# Test DynamoDB functionality
python test_dynamodb.py

# Test image management
python test_image_management.py

# Test medical details display
python test_medical_details.py
```

## 📁 Project Structure

```
medical-ocr-system/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── create_dynamodb_table.py    # Database setup
├── .env.example               # Environment template
├── templates/                 # HTML templates
│   ├── enhanced_voting_ocr.html  # Main interface
│   ├── images_list.html          # Image management
│   └── ...                       # Other templates
├── deploy/                    # AWS deployment configs
│   ├── quick_deploy.sh           # AWS setup script
│   └── apprunner-config.yaml     # App Runner config
└── test_*.py                  # Test scripts
```

## 🔒 Security Features

- **AWS IAM**: Role-based access control
- **Environment Variables**: Secure configuration management
- **Input Validation**: File type and size restrictions
- **Error Handling**: Comprehensive error management
- **Health Monitoring**: Built-in health check endpoint

## 📈 Performance

- **Processing Speed**: 1-3 seconds per document
- **Accuracy**: High with multi-model voting system
- **Scalability**: Auto-scaling with AWS App Runner
- **Storage**: Efficient with DynamoDB + S3 architecture

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- **AWS Setup**: See [AWS_PROFILE_SETUP.md](./AWS_PROFILE_SETUP.md)
- **Issues**: Create GitHub issues for bugs or feature requests

## 🎯 Version

**Current Version**: v1.2.0 - Production Ready with Medical Details Display

**Features in this version**:
- ✅ Multi-model AI OCR processing
- ✅ Human-in-the-loop review system
- ✅ Complete image management
- ✅ Detailed medical content display
- ✅ AWS App Runner deployment ready
- ✅ Production monitoring and health checks

---

**🏥 Built for medical professionals to efficiently process and manage medical document OCR with AI assistance and human oversight.**
