"""
Enhanced Dynamic Tool Retriever MCP Chatbot Demo

This demo works with both real and mock A2A agents to showcase the Dynamic Tool Retriever MCP system.
"""

import gradio as gr
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import sys
import os

# Import mock agent
from mock_agent import MockA2AClient, MockMCPResponse

# Try to import real A2A client
try:
    import httpx
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from a2a.client import A2ACardResolver, A2AClient
    from a2a.types import (
        AgentCard,
        MessageSendParams,
        SendMessageRequest,
        SendStreamingMessageRequest,
    )
    A2A_AVAILABLE = True
except ImportError:
    print("A2A libraries not available. Running in mock mode only.")
    A2A_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedMCPChatbot:
    def __init__(self, agent_url: str = "http://localhost:10000", use_mock: bool = False):
        """
        Initialize the Enhanced MCP Chatbot Demo
        
        Args:
            agent_url: URL where your LangGraph A2A agent is running
            use_mock: Force use of mock agent for demonstration
        """
        self.agent_url = agent_url
        self.use_mock = use_mock
        self.agent_card: Optional[AgentCard] = None
        self.httpx_client = None
        self.a2a_client = None
        self.mock_client = None
        self.connected = False
        
    async def initialize_connection(self) -> Tuple[bool, str]:
        """Initialize connection to agent (real or mock)"""
        if self.use_mock or not A2A_AVAILABLE:
            self.mock_client = MockA2AClient()
            self.connected = True
            return True, "Connected to Mock Agent (Demo Mode) - Simulating 14,000+ tools"
        
        try:
            self.httpx_client = httpx.AsyncClient()
            resolver = A2ACardResolver(
                httpx_client=self.httpx_client,
                base_url=self.agent_url,
            )
            
            self.agent_card = await resolver.get_agent_card()
            self.a2a_client = A2AClient(
                httpx_client=self.httpx_client, 
                agent_card=self.agent_card
            )
            self.connected = True
            
            return True, f"Connected to Real Agent: {self.agent_card.name}"
            
        except Exception as e:
            logger.warning(f"Failed to connect to real agent: {e}. Falling back to mock mode.")
            self.mock_client = MockA2AClient()
            self.connected = True
            return True, f"Connected to Mock Agent (Real agent unavailable) - {str(e)}"
    
    async def send_message(self, message: str):
        """Send message and yield streaming responses"""
        if not self.connected:
            yield {
                "type": "error",
                "content": "Not connected to any agent",
                "timestamp": datetime.now().isoformat()
            }
            return
        
        if self.mock_client:
            # Use mock client
            mock_request = type('MockRequest', (), {
                'params': type('MockParams', (), {
                    'message': {
                        'parts': [{'text': message}]
                    }
                })()
            })()
            
            async for response in self.mock_client.send_message_streaming(mock_request):
                yield response
        else:
            # Use real A2A client
            try:
                send_message_payload = {
                    'message': {
                        'role': 'user',
                        'parts': [{'kind': 'text', 'text': message}],
                        'messageId': 'demo-' + str(hash(message))[-8:],
                    },
                }
                
                streaming_request = SendStreamingMessageRequest(
                    id='demo-request-' + str(hash(message))[-8:],
                    params=MessageSendParams(**send_message_payload)
                )
                
                async for chunk in self.a2a_client.send_message_streaming(streaming_request):
                    yield {
                        "type": "agent_response",
                        "content": chunk.model_dump(mode='json', exclude_none=True),
                        "timestamp": datetime.now().isoformat()
                    }
                    
            except Exception as e:
                yield {
                    "type": "error",
                    "content": f"Error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }

def create_enhanced_demo(agent_url: str = "http://localhost:10000", use_mock: bool = False):
    """Create the enhanced Gradio demo interface"""
    
    chatbot_instance = EnhancedMCPChatbot(agent_url=agent_url, use_mock=use_mock)
    
    # Custom CSS
    custom_css = """
    .demo-container { max-width: 1400px; margin: 0 auto; padding: 20px; }
    .status-panel { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px; 
        border-radius: 10px; 
        margin: 10px 0;
        text-align: center;
        font-weight: bold;
    }
    .tools-panel { 
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 20px; 
        border-radius: 10px;
        min-height: 400px;
    }
    .workflow-panel { 
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 20px; 
        border-radius: 10px;
        min-height: 400px;
    }
    .logs-panel { 
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        color: white;
        padding: 20px; 
        border-radius: 10px;
        font-family: 'Courier New', monospace;
        min-height: 300px;
    }
    .chat-container {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px;
    }
    .example-button {
        margin: 5px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 15px;
        border-radius: 5px;
        cursor: pointer;
    }
    """
    
    with gr.Blocks(
        title="🚀 Dynamic Tool Retriever MCP Demo",
        theme=gr.themes.Soft(),
        css=custom_css
    ) as demo:
        
        gr.HTML("""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; margin-bottom: 20px;">
            <h1>🚀 Dynamic Tool Retriever MCP</h1>
            <h2>Interactive Chatbot Demo</h2>
            <p style="font-size: 18px;">Experience AI-powered tool discovery with 14,000+ tools from 4,000+ MCP servers</p>
        </div>
        """)
        
        # Metrics display
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="metric-card">
                    <h3>🔧 Available Tools</h3>
                    <h2 style="color: #667eea;">14,000+</h2>
                    <p>Across all domains</p>
                </div>
                """)
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="metric-card">
                    <h3>🌐 MCP Servers</h3>
                    <h2 style="color: #667eea;">4,000+</h2>
                    <p>Active server registry</p>
                </div>
                """)
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="metric-card">
                    <h3>⚡ Response Time</h3>
                    <h2 style="color: #667eea;">< 2s</h2>
                    <p>Vector similarity search</p>
                </div>
                """)
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="metric-card">
                    <h3>🎯 Accuracy</h3>
                    <h2 style="color: #667eea;">95%+</h2>
                    <p>Tool relevance matching</p>
                </div>
                """)
        
        # Connection status
        connection_status = gr.Markdown(
            "🔄 **Status:** Initializing connection...",
            elem_classes=["status-panel"]
        )
        
        # Main interface
        with gr.Row():
            with gr.Column(scale=2, elem_classes=["chat-container"]):
                gr.Markdown("## 💬 Chat Interface")
                
                chatbot = gr.Chatbot(
                    height=450,
                    show_label=False,
                    bubble_full_width=False,
                    avatar_images=("👤", "🤖")
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Describe any task and watch the magic happen...",
                        label="Your Task Description",
                        lines=2,
                        scale=4
                    )
                    send_btn = gr.Button("🚀 Execute", variant="primary", scale=1)
                
                clear_btn = gr.Button("🗑️ Clear Chat", variant="secondary")
        
        # Results panels
        with gr.Row():
            with gr.Column(scale=1):
                tools_output = gr.Markdown(
                    """
                    ## 🔧 Retrieved Tools
                    
                    *Send a message to see dynamic tool retrieval in action!*
                    
                    The system will:
                    - Query 14,000+ available tools
                    - Use vector similarity search
                    - Rank by relevance score
                    - Return top matches
                    """,
                    elem_classes=["tools-panel"]
                )
            
            with gr.Column(scale=1):
                workflow_output = gr.Markdown(
                    """
                    ## 📋 AI-Generated Workflow
                    
                    *Workflow steps will appear here!*
                    
                    Features:
                    - Task decomposition
                    - Step-by-step execution plan
                    - Tool coordination
                    - Dependency management
                    """,
                    elem_classes=["workflow-panel"]
                )
        
        # MCP Communication logs
        with gr.Row():
            logs_output = gr.Markdown(
                """
                ## 📡 Real-time MCP Communication Logs
                
                *Live system logs will appear here...*
                
                - Neo4j vector database queries
                - Tool retrieval operations  
                - Workflow generation steps
                - Performance metrics
                """,
                elem_classes=["logs-panel"]
            )
        
        # Example queries
        gr.Markdown("## 💡 Try These Example Tasks")
        
        example_queries = [
            "Create a complete data analysis pipeline for customer sales data",
            "Build a web scraping system for e-commerce product monitoring", 
            "Set up a machine learning pipeline for sentiment analysis",
            "Design a CI/CD workflow for a Python web application",
            "Create an automated report generation system",
            "Build a real-time data processing pipeline with Apache Kafka",
            "Set up monitoring and alerting for a microservices architecture"
        ]
        
        with gr.Row():
            for i in range(0, len(example_queries), 2):
                with gr.Column():
                    if i < len(example_queries):
                        gr.Button(
                            example_queries[i], 
                            elem_classes=["example-button"]
                        ).click(
                            lambda x=example_queries[i]: x,
                            outputs=msg_input
                        )
                    if i + 1 < len(example_queries):
                        gr.Button(
                            example_queries[i + 1],
                            elem_classes=["example-button"] 
                        ).click(
                            lambda x=example_queries[i + 1]: x,
                            outputs=msg_input
                        )
        
        # Event handlers
        async def process_message(message, history):
            """Process user message and stream responses"""
            if not message.strip():
                yield history, "", "Please enter a message", "", ""
                return
            
            # Add user message
            history.append([message, "🔄 Analyzing task and retrieving tools..."])
            
            # Collect responses
            agent_response = ""
            tools_data = []
            workflow_data = []
            logs_data = []
            
            try:
                async for response in chatbot_instance.send_message(message):
                    if response["type"] == "agent_response":
                        content = response["content"]
                        if isinstance(content, dict):
                            agent_response = content.get("agent_response", "")
                            tools_data = content.get("tools_retrieved", [])
                            workflow_data = content.get("workflow_generated", [])
                            logs_data = content.get("mcp_logs", [])
                    elif response["type"] == "status":
                        # Update the last message with status
                        history[-1][1] = response["content"]
                        yield history, "", format_tools_display(tools_data), format_workflow_display(workflow_data), format_logs_display(logs_data)
                
                # Final update
                history[-1][1] = agent_response or "Task analysis complete!"
                
            except Exception as e:
                history[-1][1] = f"❌ Error: {str(e)}"
            
            yield history, "", format_tools_display(tools_data), format_workflow_display(workflow_data), format_logs_display(logs_data)
        
        def format_tools_display(tools_data):
            """Format tools data for display"""
            if not tools_data:
                return """
                ## 🔧 Retrieved Tools
                
                *No tools retrieved yet.*
                """
            
            formatted = "## 🔧 Retrieved Tools from 14,000+ Database\n\n"
            for i, tool in enumerate(tools_data, 1):
                formatted += f"""
### {i}. **{tool.get('tool_name', 'Unknown')}**
- **Score:** {tool.get('score', 'N/A')} 
- **Vendor:** {tool.get('vendor', 'Unknown')}
- **Description:** {tool.get('description', 'No description')}
- **Parameters:** `{tool.get('input_parameters', 'None')}`

---
"""
            return formatted
        
        def format_workflow_display(workflow_data):
            """Format workflow data for display"""
            if not workflow_data:
                return """
                ## 📋 AI-Generated Workflow
                
                *Workflow will be generated based on your task.*
                """
            
            formatted = "## 📋 AI-Generated Execution Workflow\n\n"
            for step in workflow_data:
                formatted += f"""
### Step {step.get('step', '?')}: {step.get('action', 'Unknown')}
- **Tool:** {step.get('tool', 'N/A')}
- **Description:** {step.get('description', 'No description')}
- **Output:** {step.get('expected_output', 'Not specified')}

---
"""
            return formatted
        
        def format_logs_display(logs_data):
            """Format logs data for display"""
            if not logs_data:
                return """
                ## 📡 MCP Communication Logs
                
                *Real-time logs will appear here...*
                """
            
            formatted = "## 📡 Real-time MCP Communication Logs\n\n"
            for log in logs_data:
                formatted += f"""
**[{log.get('timestamp', 'N/A')}]** {log.get('action', 'Unknown')}
```
{log.get('details', 'No details')}
```

"""
            return formatted
        
        async def initialize_connection():
            """Initialize connection to agent"""
            success, message = await chatbot_instance.initialize_connection()
            status_emoji = "🟢" if success else "🔴"
            return f"{status_emoji} **Status:** {message}"
        
        # Initialize connection on load
        demo.load(initialize_connection, outputs=[connection_status])
        
        # Message sending
        send_btn.click(
            process_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input, tools_output, workflow_output, logs_output]
        )
        
        msg_input.submit(
            process_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input, tools_output, workflow_output, logs_output]
        )
        
        # Clear chat
        clear_btn.click(
            lambda: ([], "", "", ""),
            outputs=[chatbot, tools_output, workflow_output, logs_output]
        )
    
    return demo

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Dynamic Tool Retriever MCP Demo")
    parser.add_argument("--agent-url", default="http://localhost:10000", 
                       help="URL of the LangGraph A2A agent")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", default=7860, type=int, help="Port to run on")
    parser.add_argument("--share", action="store_true", help="Create public link")
    parser.add_argument("--mock", action="store_true", help="Force mock mode")
    
    args = parser.parse_args()
    
    print("🚀 Starting Enhanced Dynamic Tool Retriever MCP Demo")
    print(f"🎯 Agent URL: {args.agent_url}")
    print(f"🌐 Demo URL: http://{args.host}:{args.port}")
    print(f"🎭 Mock Mode: {'Enabled' if args.mock else 'Auto-detect'}")
    
    demo = create_enhanced_demo(agent_url=args.agent_url, use_mock=args.mock)
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=True
    )
