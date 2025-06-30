#!/bin/bash

# GitHub Repository Setup Script
# This script helps you connect your local repository to GitHub

set -e

echo "🚀 Medical OCR System - GitHub Setup"
echo "===================================="
echo ""

# Get GitHub username
read -p "Enter your GitHub username: " GITHUB_USERNAME

if [ -z "$GITHUB_USERNAME" ]; then
    echo "❌ GitHub username is required"
    exit 1
fi

REPO_NAME="medical-ocr-system"
REPO_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo ""
echo "📋 Repository Information:"
echo "  Username: $GITHUB_USERNAME"
echo "  Repository: $REPO_NAME"
echo "  URL: $REPO_URL"
echo ""

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "❌ Error: Git repository not initialized. Please run 'git init' first."
    exit 1
fi

# Check if remote already exists
if git remote get-url origin &> /dev/null; then
    echo "⚠️ Remote 'origin' already exists:"
    git remote get-url origin
    read -p "Do you want to replace it? (y/N): " REPLACE_REMOTE
    
    if [[ $REPLACE_REMOTE =~ ^[Yy]$ ]]; then
        git remote remove origin
        echo "✅ Removed existing remote"
    else
        echo "❌ Aborted. Please remove the existing remote manually if needed."
        exit 1
    fi
fi

echo ""
echo "🔧 Setting up GitHub repository..."

# Add remote
echo "📡 Adding remote repository..."
git remote add origin "$REPO_URL"
echo "✅ Remote added: $REPO_URL"

# Ensure we're on main branch
echo "🌿 Ensuring main branch..."
git branch -M main
echo "✅ Branch set to main"

# Show current status
echo ""
echo "📊 Current Git Status:"
git status --short

echo ""
echo "📋 Ready to push to GitHub!"
echo ""
echo "⚠️  IMPORTANT: Before running the push command, make sure you have:"
echo "   1. Created the repository '$REPO_NAME' on GitHub"
echo "   2. Set the repository to PUBLIC (required for App Runner free tier)"
echo "   3. Do NOT initialize with README, .gitignore, or license"
echo ""

read -p "Have you created the GitHub repository? (y/N): " REPO_CREATED

if [[ $REPO_CREATED =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Pushing to GitHub..."
    
    # Push to GitHub
    if git push -u origin main; then
        echo ""
        echo "🎉 Successfully pushed to GitHub!"
        echo ""
        echo "🔗 Repository URL: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
        echo ""
        echo "✅ Next Steps:"
        echo "   1. Visit your repository on GitHub to verify all files are uploaded"
        echo "   2. Follow the DEPLOYMENT_GUIDE.md for AWS App Runner deployment"
        echo "   3. Run './deploy/quick_deploy.sh' to set up AWS resources"
        echo ""
    else
        echo ""
        echo "❌ Push failed. Common issues:"
        echo "   - Repository doesn't exist on GitHub"
        echo "   - Authentication failed (you may need a personal access token)"
        echo "   - Network connectivity issues"
        echo ""
        echo "💡 Manual push command:"
        echo "   git push -u origin main"
    fi
else
    echo ""
    echo "📝 Manual Steps:"
    echo "   1. Go to https://github.com/new"
    echo "   2. Repository name: $REPO_NAME"
    echo "   3. Description: Medical OCR System with AWS Bedrock"
    echo "   4. Set to PUBLIC"
    echo "   5. Do NOT initialize with any files"
    echo "   6. Create repository"
    echo "   7. Run this script again"
    echo ""
    echo "💡 Or push manually:"
    echo "   git push -u origin main"
fi

echo ""
echo "📚 For detailed instructions, see: GITHUB_SETUP.md"
