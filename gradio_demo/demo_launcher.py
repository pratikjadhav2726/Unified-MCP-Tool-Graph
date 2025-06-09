#!/usr/bin/env python3
"""
Simple demo script to test the Gradio UI without complex dependencies
"""

import sys
import os
import subprocess

def main():
    print("🚀 Dynamic Tool Retriever MCP Demo Launcher")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Change to demo directory
    demo_dir = os.path.join(os.path.dirname(__file__), 'gradio_demo')
    os.chdir(demo_dir)
    
    # Install requirements
    print("📦 Installing requirements...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'gradio', 'asyncio'], check=True)
        print("✅ Requirements installed")
    except subprocess.CalledProcessError:
        print("⚠️ Warning: Could not install some requirements")
    
    # Run the demo
    print("🎭 Starting demo in mock mode...")
    print("🌐 Demo will be available at: http://localhost:7860")
    print("📝 This showcases the full MCP system functionality")
    
    try:
        subprocess.run([sys.executable, 'enhanced_demo.py', '--mock'], check=True)
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")
    except Exception as e:
        print(f"❌ Error running demo: {e}")

if __name__ == "__main__":
    main()
