# AWS Profile Setup Guide

Using AWS profiles is the **recommended and secure way** to manage AWS credentials for this application.

## 🔐 **Why Use AWS Profiles?**

✅ **Security**: No hardcoded credentials in code or environment files
✅ **Flexibility**: Easy switching between different AWS accounts/roles
✅ **Best Practice**: Follows AWS security recommendations
✅ **Convenience**: Automatic credential management

## 🚀 **Quick Setup**

### **Option 1: Default Profile (Simplest)**

1. **Configure AWS CLI:**
   ```bash
   aws configure
   ```
   
2. **Enter your credentials:**
   ```
   AWS Access Key ID: YOUR_ACCESS_KEY
   AWS Secret Access Key: YOUR_SECRET_KEY
   Default region name: us-east-1
   Default output format: json
   ```

3. **Set environment variables:**
   ```bash
   # In your .env file
   AWS_PROFILE=default
   AWS_REGION=us-east-1
   S3_BUCKET=medical-ocr-documents
   ```

### **Option 2: Named Profile (Recommended)**

1. **Create a named profile:**
   ```bash
   aws configure --profile medical-ocr
   ```

2. **Set environment variables:**
   ```bash
   # In your .env file
   AWS_PROFILE=medical-ocr
   AWS_REGION=us-east-1
   S3_BUCKET=medical-ocr-documents
   ```

### **Option 3: Multiple Profiles**

```bash
# Development environment
aws configure --profile dev-medical-ocr

# Production environment  
aws configure --profile prod-medical-ocr

# Testing environment
aws configure --profile test-medical-ocr
```

Then switch profiles by changing the `.env` file:
```bash
# For development
AWS_PROFILE=dev-medical-ocr

# For production
AWS_PROFILE=prod-medical-ocr
```

## 📁 **AWS Credentials File Location**

Your credentials are stored in:
- **macOS/Linux**: `~/.aws/credentials`
- **Windows**: `C:\Users\USERNAME\.aws\credentials`

Example credentials file:
```ini
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

[medical-ocr]
aws_access_key_id = AKIAI44QH8DHBEXAMPLE
aws_secret_access_key = je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY

[prod-medical-ocr]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

## 🔧 **Configuration File**

AWS config file (`~/.aws/config`):
```ini
[default]
region = us-east-1
output = json

[profile medical-ocr]
region = us-east-1
output = json

[profile prod-medical-ocr]
region = us-west-2
output = json
```

## 🎯 **Application Configuration**

### **Your .env file should look like:**
```bash
# AWS Configuration - Using Profile (RECOMMENDED)
AWS_PROFILE=medical-ocr
AWS_REGION=us-east-1
S3_BUCKET=medical-ocr-documents

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# Optional: Specific Nova model
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

### **No Access Keys Needed!**
Notice there are **NO** `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in the `.env` file when using profiles.

## 🧪 **Testing Your Setup**

1. **Test AWS CLI:**
   ```bash
   aws sts get-caller-identity --profile medical-ocr
   ```

2. **Test with the application:**
   ```bash
   cd /Users/buckylee/Documents/playground/rpa_ocr
   python setup.py
   ```

3. **Expected output:**
   ```
   🔑 Using AWS profile: medical-ocr
   ✅ AWS credentials configured for: arn:aws:iam::123456789012:user/your-username
   📍 Region: us-east-1
   ```

## 🏢 **Advanced Setups**

### **IAM Roles (EC2/Lambda)**

If running on AWS infrastructure, you can use IAM roles instead:
```bash
# .env file - no profile needed
AWS_REGION=us-east-1
S3_BUCKET=medical-ocr-documents
# AWS_PROFILE is not set - will use IAM role automatically
```

### **Cross-Account Access**

For accessing resources in different AWS accounts:
```ini
# ~/.aws/config
[profile cross-account-medical]
role_arn = arn:aws:iam::ACCOUNT-B:role/MedicalOCRRole
source_profile = default
region = us-east-1
```

### **MFA (Multi-Factor Authentication)**

For enhanced security:
```ini
# ~/.aws/config
[profile medical-ocr-mfa]
role_arn = arn:aws:iam::123456789012:role/MedicalOCRRole
source_profile = default
mfa_serial = arn:aws:iam::123456789012:mfa/your-username
region = us-east-1
```

## 🔍 **Troubleshooting**

### **Common Issues:**

1. **"Profile not found" error:**
   ```bash
   # Check available profiles
   aws configure list-profiles
   
   # Verify profile exists
   cat ~/.aws/credentials
   ```

2. **"Access Denied" error:**
   ```bash
   # Test credentials
   aws sts get-caller-identity --profile your-profile-name
   
   # Check permissions
   aws iam get-user --profile your-profile-name
   ```

3. **"Region not found" error:**
   ```bash
   # Set region in config
   aws configure set region us-east-1 --profile your-profile-name
   ```

### **Debug Commands:**

```bash
# Show current configuration
aws configure list --profile medical-ocr

# Show all profiles
aws configure list-profiles

# Test specific service access
aws s3 ls --profile medical-ocr
aws bedrock list-foundation-models --region us-east-1 --profile medical-ocr
```

## 🛡️ **Security Best Practices**

1. **Use IAM roles** when possible (EC2, Lambda, ECS)
2. **Rotate access keys** regularly
3. **Use least-privilege permissions**
4. **Enable MFA** for sensitive operations
5. **Never commit credentials** to version control
6. **Use different profiles** for different environments

## 🚀 **Ready to Deploy**

Once your AWS profile is configured:

```bash
cd /Users/buckylee/Documents/playground/rpa_ocr
cp .env.example .env
# Edit .env to set AWS_PROFILE=your-profile-name
./run.sh --setup
```

Your application will automatically use the AWS profile credentials - no access keys needed in your code or environment files!

## 📞 **Need Help?**

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your AWS permissions
3. Test with AWS CLI first
4. Check the application logs for specific error messages

**AWS profiles are the secure, professional way to handle AWS credentials. Your application is now ready for secure deployment!**
