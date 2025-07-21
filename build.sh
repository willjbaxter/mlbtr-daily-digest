#!/bin/bash

# MLBTR Daily Digest Build Script
# This script is used by hosting platforms to build the site

echo "🏗️  Building MLBTR Daily Digest..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Generate all summaries
echo "📊 Generating summaries..."
python mlbtr_daily_summary.py --regenerate-all

echo "✅ Build complete! Output available in ./out/" 