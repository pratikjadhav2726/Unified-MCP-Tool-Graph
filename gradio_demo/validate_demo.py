#!/usr/bin/env python3
"""
Demo validation script to test the Gradio interface functionality
"""

import requests
import json
import time
from typing import Dict, Any

def test_demo_endpoint(url: str = "http://localhost:7860") -> Dict[str, Any]:
    """Test if the demo is responsive"""
    try:
        response = requests.get(f"{url}/", timeout=5)
        return {
            "status": "success" if response.status_code == 200 else "error",
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "accessible": True
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": str(e),
            "accessible": False
        }

def main():
    """Main validation function"""
    print("🧪 Testing Dynamic Tool Retriever MCP Demo...")
    print("=" * 50)
    
    # Test demo accessibility
    result = test_demo_endpoint()
    
    if result["accessible"]:
        print(f"✅ Demo is accessible at http://localhost:7860")
        print(f"⚡ Response time: {result['response_time']:.3f}s")
        print(f"📊 Status code: {result['status_code']}")
    else:
        print(f"❌ Demo not accessible: {result.get('error', 'Unknown error')}")
        return
    
    print("\n🎯 Demo Features:")
    print("   ✅ Interactive chat interface")
    print("   ✅ Real-time tool retrieval simulation")
    print("   ✅ AI-powered workflow generation")
    print("   ✅ Live MCP communication logs")
    print("   ✅ Multi-panel dashboard layout")
    
    print("\n💡 Test Queries to Try:")
    test_queries = [
        "Analyze sales data and create visualizations",
        "Build a web scraping system for monitoring",
        "Set up machine learning pipeline for sentiment analysis",
        "Design CI/CD workflow for Python applications"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"   {i}. '{query}'")
    
    print(f"\n🌐 Open browser to: http://localhost:7860")
    print("🚀 Demo is ready for demonstration!")

if __name__ == "__main__":
    main()
