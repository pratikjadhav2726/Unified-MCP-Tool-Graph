#!/bin/bash

# MCP Unified Gateway Startup Script
# This script provides an easy way to start the unified MCP gateway system

echo "🚀 Starting MCP Unified Gateway System..."
echo "========================================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "start_unified_gateway.py" ]; then
    echo "❌ start_unified_gateway.py not found."
    echo "Please run this script from the project root directory."
    exit 1
fi

# Run the Python startup script
python3 start_unified_gateway.py

echo "👋 Gateway system stopped."