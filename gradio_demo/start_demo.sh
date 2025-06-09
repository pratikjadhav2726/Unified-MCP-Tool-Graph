#!/bin/bash

# Dynamic Tool Retriever MCP Demo Startup Script

echo "🚀 Dynamic Tool Retriever MCP Demo Startup"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing requirements..."
pip install -r gradio_demo/requirements.txt

# Check if A2A agent is running
echo "🔍 Checking if A2A agent is available..."
if curl -s http://localhost:10000/.well-known/agent.json > /dev/null 2>&1; then
    echo "✅ A2A agent detected at http://localhost:10000"
    echo "🎯 Starting demo with real agent connection..."
    python gradio_demo/enhanced_demo.py --host 0.0.0.0 --port 7860
else
    echo "⚠️  A2A agent not detected. Starting in mock mode..."
    echo "💡 To use the real agent, start it first with:"
    echo "   python -m Example_Agents.Langgraph --host localhost --port 10000"
    echo ""
    echo "🎭 Starting demo in mock mode (still shows full functionality)..."
    python gradio_demo/enhanced_demo.py --host 0.0.0.0 --port 7860 --mock
fi
