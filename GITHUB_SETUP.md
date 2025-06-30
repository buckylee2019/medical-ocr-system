# 🚀 GitHub Repository Setup Guide

## 📋 Repository Information
- **Name**: `medical-ocr-system`
- **Description**: Medical OCR System with AWS Bedrock - Extract and process handwritten text from medical documents using Claude AI models
- **Visibility**: Public (recommended for App Runner deployment)

## 🔧 Step-by-Step Setup

### Step 1: Create GitHub Repository
1. Go to [GitHub.com](https://github.com)
2. Click the **"+"** button in the top right corner
3. Select **"New repository"**
4. Fill in the details:
   - **Repository name**: `medical-ocr-system`
   - **Description**: `Medical OCR System with AWS Bedrock - Extract and process handwritten text from medical documents using Claude AI models`
   - **Visibility**: ✅ Public (required for App Runner free tier)
   - **Initialize**: ❌ Do NOT initialize with README (we already have files)
5. Click **"Create repository"**

### Step 2: Connect Local Repository
After creating the repository, GitHub will show you commands. Use these:

```bash
# Navigate to your project directory
cd /Users/buckylee/Documents/playground/rpa_ocr

# Add the remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/medical-ocr-system.git

# Rename the default branch to main (if needed)
git branch -M main

# Push the code to GitHub
git push -u origin main
```

### Step 3: Verify Upload
1. Refresh your GitHub repository page
2. You should see all your files uploaded
3. Verify the following key files are present:
   - ✅ `app.py`
   - ✅ `requirements.txt`
   - ✅ `deploy/apprunner-config.yaml`
   - ✅ `deploy/quick_deploy.sh`
   - ✅ `DEPLOYMENT_GUIDE.md`
   - ✅ `templates/` directory

## 🎯 Quick Commands (Copy & Paste)

Replace `YOUR_USERNAME` with your actual GitHub username:

```bash
# Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/medical-ocr-system.git

# Push to GitHub
git push -u origin main
```

## 🔍 Troubleshooting

### Issue: Authentication Failed
```bash
# If you get authentication errors, you may need to use a personal access token
# Go to GitHub Settings > Developer settings > Personal access tokens
# Create a new token with 'repo' permissions
# Use the token as your password when prompted
```

### Issue: Repository Already Exists
```bash
# If you already created a repository with the same name, either:
# 1. Delete the existing repository on GitHub, or
# 2. Use a different name:
git remote add origin https://github.com/YOUR_USERNAME/medical-ocr-app.git
```

### Issue: Branch Name Mismatch
```bash
# If GitHub expects 'master' but you have 'main':
git branch -M main
git push -u origin main
```

## ✅ Success Indicators

After successful push, you should see:
- All files visible on GitHub
- Green checkmarks for successful commits
- Repository ready for App Runner deployment

## 🚀 Next Steps

Once your code is on GitHub:
1. Follow the [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
2. Run `./deploy/quick_deploy.sh` to set up AWS resources
3. Create App Runner service and connect to your GitHub repository
4. Deploy and enjoy your Medical OCR System!

---
**Note**: Keep your repository public for App Runner free tier, or ensure you have the appropriate GitHub plan for private repositories.
