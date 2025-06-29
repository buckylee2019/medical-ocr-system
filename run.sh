#!/bin/bash

# Medical OCR Web Application Startup Script

echo "🚀 Starting Medical OCR Web Application"
echo "======================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your AWS credentials before running the app"
    echo "💡 You can edit it with: nano .env"
    read -p "Press Enter to continue after editing .env file..."
fi

# Run setup if requested
if [ "$1" = "--setup" ]; then
    echo "🔧 Running AWS setup..."
    python setup.py
fi

# Start the application
echo "🌐 Starting Flask application..."
echo "📱 Open http://localhost:5000 in your browser"
echo "🛑 Press Ctrl+C to stop the server"
echo ""

python app.py
