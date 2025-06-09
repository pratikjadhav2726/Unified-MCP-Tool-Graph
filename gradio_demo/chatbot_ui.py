"""
Dynamic Tool Retriever MCP - Gradio Chatbot Demo

This demo showcases the Dynamic Tool Retriever MCP system with a LangGraph A2A agent
that can access 14,000+ tools from 4,000+ MCP servers.
"""

import gradio as gr
import asyncio
import json
import httpx
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
from datetime import datetime
import sys
import os

# Add parent directory to path to import A2A client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from a2a.client import A2ACardResolver, A2AClient
    from a2a.types import (
        AgentCard,
        MessageSendParams,
        SendMessageRequest,
        SendStreamingMessageRequest,
    )
    A2A_AVAILABLE = True
except ImportError:
    print("Warning: A2A libraries not available. Using mock mode.")
    A2A_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPChatbotDemo:
    def __init__(self, agent_url: str = "http://localhost:10000"):
        """
        Initialize the MCP Dynamic Tool Retriever Chatbot Demo
        
        Args:
            agent_url: URL where your LangGraph A2A agent is running
        """
        self.agent_url = agent_url
        self.agent_card: Optional[AgentCard] = None
        self.httpx_client = None
        self.a2a_client = None
        self.chat_history = []
        self.tool_calls_log = []
        self.workflow_steps = []
        
    async def initialize_agent_connection(self) -> Tuple[bool, str]:
        """Initialize connection to the A2A agent"""
        try:
            if not A2A_AVAILABLE:
                return False, "A2A libraries not available. Running in mock mode."
            
            self.httpx_client = httpx.AsyncClient()
            resolver = A2ACardResolver(
                httpx_client=self.httpx_client,
                base_url=self.agent_url,
            )
            
            # Fetch agent card
            self.agent_card = await resolver.get_agent_card()
            
            # Initialize A2A client
            self.a2a_client = A2AClient(
                httpx_client=self.httpx_client, 
                agent_card=self.agent_card
            )
            
            return True, f"Successfully connected to agent: {self.agent_card.name}"
            
        except Exception as e:
            error_msg = f"Failed to connect to agent at {self.agent_url}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def send_message_to_agent(self, message: str) -> AsyncIterable[Dict[str, Any]]:
        """Send message to the A2A agent and stream responses"""
        if not self.a2a_client:
            yield {
                "type": "error",
                "content": "Agent not connected. Please check if the agent is running.",
                "timestamp": datetime.now().isoformat()
            }
            return
        
        try:
            send_message_payload = {
                'message': {
                    'role': 'user',
                    'parts': [
                        {'kind': 'text', 'text': message}
                    ],
                    'messageId': uuid4().hex,
                },
            }
            
            streaming_request = SendStreamingMessageRequest(
                id=str(uuid4()), 
                params=MessageSendParams(**send_message_payload)
            )
            
            yield {
                "type": "status",
                "content": "🔄 Connecting to Dynamic Tool Retriever MCP...",
                "timestamp": datetime.now().isoformat()
            }
            
            stream_response = self.a2a_client.send_message_streaming(streaming_request)
            
            async for chunk in stream_response:
                chunk_data = chunk.model_dump(mode='json', exclude_none=True)
                
                # Parse the response to extract different types of information
                yield {
                    "type": "agent_response",
                    "content": chunk_data,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            yield {
                "type": "error",
                "content": f"Error communicating with agent: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def process_user_message(self, message: str) -> Tuple[str, List, str, str, str]:
        """Process user message and return formatted responses"""
        if not message.strip():
            return "", self.chat_history, "", "", ""
        
        # Add user message to chat history
        self.chat_history.append([message, "🔄 Processing..."])
        
        # Initialize response containers
        agent_responses = []
        tool_calls = []
        workflow_steps = []
        
        # Stream responses from agent
        async for response in self.send_message_to_agent(message):
            if response["type"] == "agent_response":
                agent_responses.append(response["content"])
            elif response["type"] == "tool_call":
                tool_calls.append(response)
            elif response["type"] == "workflow":
                workflow_steps.append(response)
        
        # Format the main response
        if agent_responses:
            formatted_response = self.format_agent_response(agent_responses[-1])
        else:
            formatted_response = "❌ No response received from agent"
        
        # Update chat history
        self.chat_history[-1][1] = formatted_response
        
        # Format additional panels
        tools_display = self.format_tools_panel(tool_calls)
        workflow_display = self.format_workflow_panel(workflow_steps)
        mcp_logs = self.format_mcp_logs(agent_responses)
        
        return "", self.chat_history, tools_display, workflow_display, mcp_logs
    
    def format_agent_response(self, response_data: Dict) -> str:
        """Format the agent response for display"""
        if isinstance(response_data, dict):
            # Extract meaningful content from the response
            content = response_data.get('result', {}).get('content', '')
            if not content:
                content = str(response_data)
            
            return f"## 🤖 Agent Response\n\n{content}"
        else:
            return f"## 🤖 Agent Response\n\n{str(response_data)}"
    
    def format_tools_panel(self, tool_calls: List[Dict]) -> str:
        """Format tool calls for the tools panel"""
        if not tool_calls:
            return "## 🔧 Retrieved Tools\n\n*No tools retrieved yet. Send a message to see dynamic tool retrieval in action.*"
        
        formatted = "## 🔧 Retrieved Tools from 14,000+ Available\n\n"
        
        for i, tool in enumerate(tool_calls, 1):
            formatted += f"### {i}. **{tool.get('tool_name', 'Unknown Tool')}**\n"
            formatted += f"**Similarity Score:** {tool.get('score', 'N/A')}\n"
            formatted += f"**Description:** {tool.get('description', 'No description')}\n"
            formatted += f"**Vendor:** {tool.get('vendor', 'Unknown')}\n"
            formatted += "\n---\n\n"
        
        return formatted
    
    def format_workflow_panel(self, workflow_steps: List[Dict]) -> str:
        """Format workflow steps for display"""
        if not workflow_steps:
            return "## 📋 Generated Workflow\n\n*Workflow will appear here when the agent processes your request.*"
        
        formatted = "## 📋 AI-Generated Workflow\n\n"
        
        for i, step in enumerate(workflow_steps, 1):
            formatted += f"### Step {i}: {step.get('action', 'Unknown Action')}\n"
            formatted += f"**Tool:** {step.get('tool', 'N/A')}\n"
            formatted += f"**Description:** {step.get('description', 'No description')}\n"
            formatted += "\n---\n\n"
        
        return formatted
    
    def format_mcp_logs(self, responses: List[Dict]) -> str:
        """Format MCP communication logs"""
        formatted = "## 📡 MCP Communication Logs\n\n"
        
        for i, response in enumerate(responses, 1):
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted += f"**[{timestamp}] Response {i}:**\n"
            formatted += f"```json\n{json.dumps(response, indent=2)}\n```\n\n"
        
        return formatted
    
    async def cleanup(self):
        """Clean up resources"""
        if self.httpx_client:
            await self.httpx_client.aclose()

def create_demo_interface():
    """Create the Gradio interface"""
    
    demo_instance = MCPChatbotDemo()
    
    # Custom CSS for better styling
    custom_css = """
    .main-container { max-width: 1400px; margin: 0 auto; }
    .status-panel { background: #e3f2fd; padding: 15px; border-radius: 8px; }
    .tools-panel { background: #f3e5f5; padding: 15px; border-radius: 8px; }
    .workflow-panel { background: #e8f5e9; padding: 15px; border-radius: 8px; }
    .logs-panel { background: #fff3e0; padding: 15px; border-radius: 8px; font-family: monospace; }
    .connection-status { padding: 10px; border-radius: 5px; margin: 10px 0; }
    .connected { background: #d4edda; color: #155724; }
    .disconnected { background: #f8d7da; color: #721c24; }
    """
    
    with gr.Blocks(
        title="Dynamic Tool Retriever MCP Demo",
        theme=gr.themes.Soft(),
        css=custom_css
    ) as demo:
        
        # Header
        gr.Markdown("""
        # 🚀 Dynamic Tool Retriever MCP - Chatbot Demo
        
        ## Experience the power of dynamic tool retrieval with 14,000+ tools from 4,000+ MCP servers!
        
        This demo showcases:
        - **LangGraph A2A Agent** - Intelligent task decomposition and tool selection
        - **Dynamic Tool Retrieval** - Real-time tool discovery using vector similarity search  
        - **Workflow Generation** - AI-generated step-by-step execution plans
        - **MCP Integration** - Seamless integration with Model Context Protocol servers
        """)
        
        # Connection status
        connection_status = gr.Markdown(
            "🔴 **Status:** Not connected to agent", 
            elem_classes=["connection-status", "disconnected"]
        )
        
        # Main chat interface
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    height=500,
                    label="💬 Chat with Dynamic Tool Retriever Agent",
                    show_label=True,
                    bubble_full_width=False
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Ask me to help with any task... (e.g., 'Help me create a data analysis pipeline')",
                        label="Your Message",
                        lines=3,
                        scale=4
                    )
                    send_btn = gr.Button("🚀 Send", variant="primary", scale=1)
        
        # Information panels
        with gr.Row():
            with gr.Column(scale=1):
                tools_panel = gr.Markdown(
                    "## 🔧 Retrieved Tools\n\n*Tools will appear here when you send a message*",
                    elem_classes=["tools-panel"]
                )
            
            with gr.Column(scale=1):
                workflow_panel = gr.Markdown(
                    "## 📋 Generated Workflow\n\n*Workflow steps will appear here*",
                    elem_classes=["workflow-panel"]
                )
        
        # Logs panel
        with gr.Row():
            logs_panel = gr.Markdown(
                "## 📡 MCP Communication Logs\n\n*Real-time logs will appear here*",
                elem_classes=["logs-panel"]
            )
        
        # Examples
        gr.Examples(
            examples=[
                "Help me create a data analysis pipeline for sales data",
                "I need to build a web scraper for product information",
                "Create a machine learning workflow for text classification",
                "Set up a CI/CD pipeline for my Python project", 
                "Help me process and analyze customer feedback data",
                "I want to create visualizations from my database",
                "Build an API for my application with proper authentication"
            ],
            inputs=msg_input,
            label="💡 Try these example queries"
        )
        
        # System info
        gr.Markdown("""
        ## 📊 System Capabilities
        
        - **14,000+ Tools** across various domains (data analysis, web scraping, ML, DevOps, etc.)
        - **4,000+ MCP Servers** providing specialized functionality
        - **Vector Similarity Search** for intelligent tool matching using Neo4j
        - **Real-time Workflow Generation** based on task analysis
        - **A2A Protocol** for seamless agent-to-agent communication
        - **Streaming Responses** for real-time interaction
        """)
        
        # Event handlers
        async def handle_send(message, history):
            try:
                return await demo_instance.process_user_message(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                return "", history, f"Error: {str(e)}", "", ""
        
        async def initialize_connection():
            success, message = await demo_instance.initialize_agent_connection()
            if success:
                return f"🟢 **Status:** {message}", "connected"
            else:
                return f"🔴 **Status:** {message}", "disconnected"
        
        # Initialize connection on load
        demo.load(
            initialize_connection,
            outputs=[connection_status, gr.State()]
        )
        
        # Send button click
        send_btn.click(
            handle_send,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot, tools_panel, workflow_panel, logs_panel]
        )
        
        # Enter key press
        msg_input.submit(
            handle_send,
            inputs=[msg_input, chatbot], 
            outputs=[msg_input, chatbot, tools_panel, workflow_panel, logs_panel]
        )
    
    return demo

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Dynamic Tool Retriever MCP Chatbot Demo")
    parser.add_argument("--agent-url", default="http://localhost:10000", 
                       help="URL of the LangGraph A2A agent")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the demo to")
    parser.add_argument("--port", default=7860, type=int, help="Port to run the demo on")
    parser.add_argument("--share", action="store_true", help="Create a public Gradio link")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting Dynamic Tool Retriever MCP Demo...")
    print(f"📡 Connecting to agent at: {args.agent_url}")
    print(f"🌐 Demo will be available at: http://{args.host}:{args.port}")
    
    demo = create_demo_interface()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=True
    )
