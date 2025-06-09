#!/usr/bin/env python3
"""
Simple test demo to verify Gradio functionality
"""

import gradio as gr
import time
from typing import List, Tuple

def create_simple_demo():
    """Create a simple test demo"""
    
    def process_message(message: str, history: List[List[str]]) -> Tuple[List[List[str]], str]:
        """Process a message and return updated history"""
        # Simulate processing
        time.sleep(0.5)
        
        # Create response
        response = f"✅ Received: '{message}'\n🤖 Mock response: This is a test of the Dynamic Tool Retriever MCP system!"
        
        # Update history
        history.append([message, response])
        
        return history, ""
    
    # Create interface
    with gr.Blocks(title="MCP Demo Test") as demo:
        gr.Markdown("# 🧪 MCP Demo Test")
        gr.Markdown("Testing basic Gradio functionality")
        
        chatbot = gr.Chatbot(height=400)
        msg = gr.Textbox(placeholder="Type a test message...")
        
        msg.submit(
            process_message,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg]
        )
    
    return demo

if __name__ == "__main__":
    print("🧪 Starting test demo...")
    demo = create_simple_demo()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )
