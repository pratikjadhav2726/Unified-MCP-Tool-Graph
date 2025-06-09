"""
Final integrated demo that combines everything
"""

import gradio as gr
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import sys
import os

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockToolRetrieverDemo:
    """A complete mock demonstration of the Dynamic Tool Retriever MCP system"""
    
    def __init__(self):
        self.tools_database = self._create_mock_tools_database()
        self.chat_history = []
        
    def _create_mock_tools_database(self):
        """Create a comprehensive mock tools database"""
        return {
            "data_analysis": [
                {
                    "tool_name": "pandas_data_analyzer",
                    "description": "Advanced data analysis using pandas with statistical insights",
                    "vendor": "DataMaster Pro",
                    "score": 0.96,
                    "parameters": "file_path, analysis_type, output_format",
                    "repository": "https://github.com/datamaster/pandas-analyzer",
                    "official": True
                },
                {
                    "tool_name": "statistical_processor",
                    "description": "Statistical analysis and hypothesis testing toolkit",
                    "vendor": "StatFlow",
                    "score": 0.94,
                    "parameters": "data, test_type, confidence_level",
                    "repository": "https://github.com/statflow/processor",
                    "official": False
                },
                {
                    "tool_name": "visualization_engine",
                    "description": "Create interactive charts and dashboards",
                    "vendor": "ChartCraft",
                    "score": 0.91,
                    "parameters": "data, chart_type, styling_options",
                    "repository": "https://github.com/chartcraft/engine",
                    "official": True
                }
            ],
            "web_scraping": [
                {
                    "tool_name": "intelligent_scraper",
                    "description": "AI-powered web scraping with anti-detection",
                    "vendor": "WebHarvest",
                    "score": 0.95,
                    "parameters": "url, selectors, rate_limit, proxy_config",
                    "repository": "https://github.com/webharvest/scraper",
                    "official": True
                },
                {
                    "tool_name": "content_parser",
                    "description": "Parse and structure web content intelligently",
                    "vendor": "ParseMaster",
                    "score": 0.89,
                    "parameters": "html_content, extraction_rules",
                    "repository": "https://github.com/parsemaster/parser",
                    "official": False
                }
            ],
            "machine_learning": [
                {
                    "tool_name": "automl_classifier",
                    "description": "Automated machine learning for classification tasks",
                    "vendor": "MLFlow Pro",
                    "score": 0.97,
                    "parameters": "training_data, target_column, model_type",
                    "repository": "https://github.com/mlflow/automl",
                    "official": True
                },
                {
                    "tool_name": "feature_engineer",
                    "description": "Automated feature engineering and selection",
                    "vendor": "FeatureCraft",
                    "score": 0.92,
                    "parameters": "dataset, feature_types, selection_method",
                    "repository": "https://github.com/featurecraft/engineer",
                    "official": True
                }
            ]
        }
    
    def get_relevant_tools(self, query: str) -> List[Dict]:
        """Get relevant tools based on query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["data", "analysis", "csv", "statistics"]):
            return self.tools_database["data_analysis"]
        elif any(word in query_lower for word in ["web", "scrape", "crawl", "website"]):
            return self.tools_database["web_scraping"]
        elif any(word in query_lower for word in ["ml", "machine learning", "classification", "model"]):
            return self.tools_database["machine_learning"]
        else:
            # Return a mix of tools
            return (self.tools_database["data_analysis"][:1] + 
                   self.tools_database["web_scraping"][:1] + 
                   self.tools_database["machine_learning"][:1])
    
    def generate_workflow(self, query: str, tools: List[Dict]) -> List[Dict]:
        """Generate workflow based on query and tools"""
        workflows = {
            "data": [
                {"step": 1, "action": "Data Ingestion", "tool": tools[0]["tool_name"] if tools else "data_loader", 
                 "description": "Load and validate input data sources"},
                {"step": 2, "action": "Data Analysis", "tool": tools[1]["tool_name"] if len(tools) > 1 else "analyzer",
                 "description": "Perform comprehensive data analysis"},
                {"step": 3, "action": "Visualization", "tool": tools[2]["tool_name"] if len(tools) > 2 else "visualizer",
                 "description": "Create interactive visualizations and reports"}
            ],
            "web": [
                {"step": 1, "action": "Target Analysis", "tool": "url_analyzer",
                 "description": "Analyze target website structure"},
                {"step": 2, "action": "Data Extraction", "tool": tools[0]["tool_name"] if tools else "scraper",
                 "description": "Extract data using intelligent scraping"},
                {"step": 3, "action": "Data Processing", "tool": tools[1]["tool_name"] if len(tools) > 1 else "processor",
                 "description": "Clean and structure extracted data"}
            ],
            "ml": [
                {"step": 1, "action": "Data Preprocessing", "tool": "preprocessor",
                 "description": "Prepare data for machine learning"},
                {"step": 2, "action": "Model Training", "tool": tools[0]["tool_name"] if tools else "trainer",
                 "description": "Train and optimize ML model"},
                {"step": 3, "action": "Model Evaluation", "tool": "evaluator",
                 "description": "Evaluate model performance"}
            ]
        }
        
        # Determine workflow type
        query_lower = query.lower()
        if any(word in query_lower for word in ["data", "analysis"]):
            return workflows["data"]
        elif any(word in query_lower for word in ["web", "scrape"]):
            return workflows["web"]
        elif any(word in query_lower for word in ["ml", "machine learning"]):
            return workflows["ml"]
        else:
            return workflows["data"]  # Default

def create_comprehensive_demo():
    """Create the comprehensive demo interface"""
    
    demo_instance = MockToolRetrieverDemo()
    
    # Enhanced CSS
    css = """
    .demo-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px;
    }
    .tools-display {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        min-height: 400px;
    }
    .workflow-display {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        min-height: 400px;
    }
    .mcp-logs {
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
    }
    """
    
    with gr.Blocks(title="🚀 Dynamic Tool Retriever MCP Demo", css=css) as demo:
        
        # Header
        gr.HTML("""
        <div class="demo-header">
            <h1>🚀 Dynamic Tool Retriever MCP</h1>
            <h2>Interactive Demonstration</h2>
            <p style="font-size: 18px;">Experience AI-powered tool discovery with 14,000+ tools from 4,000+ MCP servers</p>
        </div>
        """)
        
        # Metrics
        with gr.Row():
            gr.HTML('<div class="metric-card"><h3>🔧 Tools</h3><h2 style="color: #667eea;">14,000+</h2></div>')
            gr.HTML('<div class="metric-card"><h3>🌐 Servers</h3><h2 style="color: #667eea;">4,000+</h2></div>')
            gr.HTML('<div class="metric-card"><h3>⚡ Speed</h3><h2 style="color: #667eea;">< 2s</h2></div>')
            gr.HTML('<div class="metric-card"><h3>🎯 Accuracy</h3><h2 style="color: #667eea;">95%+</h2></div>')
        
        # Main interface
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("## 💬 Chat with Dynamic Tool Retriever")
                
                chatbot = gr.Chatbot(
                    height=400,
                    show_label=False,
                    avatar_images=("👤", "🤖"),
                    type="messages"
                )
                
                msg_input = gr.Textbox(
                    placeholder="Describe any task (e.g., 'Analyze sales data and create visualizations')",
                    label="Your Task",
                    lines=2
                )
                
                send_btn = gr.Button("🚀 Execute Task", variant="primary")
                clear_btn = gr.Button("🗑️ Clear", variant="secondary")
        
        # Results panels
        with gr.Row():
            with gr.Column():
                tools_output = gr.Markdown(
                    """## 🔧 Retrieved Tools\n\n*Tools will appear here when you send a message*""",
                    elem_classes=["tools-display"]
                )
            
            with gr.Column():
                workflow_output = gr.Markdown(
                    """## 📋 AI-Generated Workflow\n\n*Workflow steps will appear here*""",
                    elem_classes=["workflow-display"]
                )
        
        # MCP logs
        mcp_logs = gr.Markdown(
            """## 📡 MCP Communication Logs\n\n*Live system logs will appear here*""",
            elem_classes=["mcp-logs"]
        )
        
        # Examples
        gr.Markdown("## 💡 Try These Examples")
        examples = gr.Examples(
            examples=[
                "Create a data analysis pipeline for customer sales data",
                "Build a web scraping system for product monitoring",
                "Set up a machine learning pipeline for sentiment analysis",
                "Design a CI/CD workflow for Python applications",
                "Create automated reporting with visualizations"
            ],
            inputs=msg_input
        )
        
        # Event handlers
        def process_message(message, history):
            if not message.strip():
                return history, "", "Please enter a message", "", ""
            
            # Simulate processing delay
            import time
            
            # Add user message
            history.append([message, "🔄 Analyzing task and querying MCP system..."])
            
            # Simulate MCP processing
            time.sleep(1)
            
            # Get tools and workflow
            tools = demo_instance.get_relevant_tools(message)
            workflow = demo_instance.generate_workflow(message, tools)
            
            # Generate response
            response = f"""## 🤖 Task Analysis Complete

I've analyzed your request: "{message}"

**Dynamic Tool Retrieval Results:**
- ✅ Queried 14,000+ tools in Neo4j database
- ✅ Found {len(tools)} highly relevant tools (similarity > 0.85)
- ✅ Generated {len(workflow)}-step execution workflow
- ✅ Tools ranked by vector similarity matching

**Next Steps:**
Follow the workflow below for optimal task execution. Each tool has been validated for compatibility and performance."""
            
            # Update chat
            history[-1][1] = response
            
            # Format displays
            tools_display = format_tools(tools)
            workflow_display = format_workflow(workflow)
            logs_display = format_logs(message, len(tools), len(workflow))
            
            return history, "", tools_display, workflow_display, logs_display
        
        def format_tools(tools):
            formatted = "## 🔧 Retrieved Tools from MCP Registry\n\n"
            for i, tool in enumerate(tools, 1):
                official_badge = "🏆 OFFICIAL" if tool.get("official") else "🔹 COMMUNITY"
                formatted += f"""
### {i}. **{tool['tool_name']}** {official_badge}
- **Similarity Score:** {tool['score']:.2f}
- **Vendor:** {tool['vendor']}
- **Description:** {tool['description']}
- **Parameters:** `{tool['parameters']}`
- **Repository:** [{tool['repository']}]({tool['repository']})

---
"""
            return formatted
        
        def format_workflow(workflow):
            formatted = "## 📋 AI-Generated Execution Workflow\n\n"
            for step in workflow:
                formatted += f"""
### Step {step['step']}: {step['action']}
- **Tool:** {step['tool']}
- **Description:** {step['description']}
- **Expected Output:** Processed data ready for next step

---
"""
            return formatted
        
        def format_logs(query, tool_count, workflow_count):
            timestamp = datetime.now().strftime("%H:%M:%S")
            return f"""## 📡 Real-time MCP Communication Logs

**[{timestamp}] QUERY_RECEIVED**
```
User Query: "{query}"
Embedding Generated: 1536-dimensional vector
```

**[{timestamp}] NEO4J_VECTOR_SEARCH**
```
Database: neo4j://localhost:7687
Index: tool_vector_index
Query Time: 0.847ms
Results: {tool_count} tools found
```

**[{timestamp}] WORKFLOW_GENERATION**
```
LLM: qwen-qwq-32b via Groq
Processing Time: 1.234s
Steps Generated: {workflow_count}
Status: SUCCESS
```

**[{timestamp}] RESPONSE_READY**
```
Total Execution Time: 1.8s
Tools Retrieved: {tool_count}/{14000}
Workflow Steps: {workflow_count}
```"""
        
        # Connect events
        send_btn.click(
            process_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input, tools_output, workflow_output, mcp_logs]
        )
        
        msg_input.submit(
            process_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input, tools_output, workflow_output, mcp_logs]
        )
        
        clear_btn.click(
            lambda: ([], "", "", ""),
            outputs=[chatbot, tools_output, workflow_output, mcp_logs]
        )
    
    return demo

if __name__ == "__main__":
    print("🚀 Starting Dynamic Tool Retriever MCP Demo")
    print("🎭 Running in demonstration mode")
    print("🌐 Demo will be available at: http://localhost:7860")
    
    demo = create_comprehensive_demo()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )
