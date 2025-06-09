"""
Mock A2A Agent for testing the Gradio demo without running the full MCP system
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime
import random

class MockMCPResponse:
    """Mock MCP response for demonstration"""
    
    @staticmethod
    def get_mock_tools(query: str) -> List[Dict[str, Any]]:
        """Generate mock tools based on query keywords"""
        tools_db = {
            "data": [
                {
                    "tool_name": "pandas_analyzer",
                    "description": "Advanced data analysis and manipulation using pandas",
                    "score": 0.95,
                    "vendor": "DataTools Pro",
                    "input_parameters": "file_path, analysis_type, columns",
                    "repository_url": "https://github.com/datatools/pandas-analyzer"
                },
                {
                    "tool_name": "statistical_processor", 
                    "description": "Statistical analysis and hypothesis testing",
                    "score": 0.92,
                    "vendor": "StatMaster",
                    "input_parameters": "data, test_type, significance_level",
                    "repository_url": "https://github.com/statmaster/processor"
                }
            ],
            "web": [
                {
                    "tool_name": "advanced_scraper",
                    "description": "Intelligent web scraping with anti-detection features",
                    "score": 0.94,
                    "vendor": "WebExtract Inc",
                    "input_parameters": "url, selectors, pagination, delay",
                    "repository_url": "https://github.com/webextract/scraper"
                },
                {
                    "tool_name": "content_parser",
                    "description": "Parse and structure web content",
                    "score": 0.89,
                    "vendor": "ParseMaster",
                    "input_parameters": "html, extraction_rules",
                    "repository_url": "https://github.com/parsemaster/parser"
                }
            ],
            "ml": [
                {
                    "tool_name": "text_classifier",
                    "description": "Advanced text classification using transformers",
                    "score": 0.96,
                    "vendor": "MLFlow Systems",
                    "input_parameters": "text_data, model_type, labels",
                    "repository_url": "https://github.com/mlflow/text-classifier"
                },
                {
                    "tool_name": "feature_engineer",
                    "description": "Automated feature engineering and selection",
                    "score": 0.91,
                    "vendor": "AutoML Pro",
                    "input_parameters": "dataset, target_column, feature_types",
                    "repository_url": "https://github.com/automl/feature-engineer"
                }
            ],
            "default": [
                {
                    "tool_name": "task_orchestrator",
                    "description": "General purpose task orchestration and workflow management",
                    "score": 0.88,
                    "vendor": "FlowMaster",
                    "input_parameters": "tasks, dependencies, execution_order",
                    "repository_url": "https://github.com/flowmaster/orchestrator"
                }
            ]
        }
        
        # Determine category based on query keywords
        query_lower = query.lower()
        if any(word in query_lower for word in ["data", "analysis", "csv", "excel", "pandas"]):
            return tools_db["data"]
        elif any(word in query_lower for word in ["web", "scrape", "crawl", "website"]):
            return tools_db["web"]
        elif any(word in query_lower for word in ["ml", "machine learning", "classification", "model"]):
            return tools_db["ml"]
        else:
            return tools_db["default"]
    
    @staticmethod
    def get_mock_workflow(query: str, tools: List[Dict]) -> List[Dict[str, Any]]:
        """Generate mock workflow based on query and tools"""
        workflows = {
            "data": [
                {
                    "step": 1,
                    "action": "Data Collection & Validation",
                    "tool": tools[0]["tool_name"] if tools else "data_collector",
                    "description": "Load and validate the input data sources",
                    "expected_output": "Clean, validated dataset ready for analysis"
                },
                {
                    "step": 2,
                    "action": "Statistical Analysis",
                    "tool": tools[1]["tool_name"] if len(tools) > 1 else "statistical_analyzer",
                    "description": "Perform comprehensive statistical analysis",
                    "expected_output": "Statistical insights and patterns identified"
                },
                {
                    "step": 3,
                    "action": "Results Visualization",
                    "tool": "visualization_engine",
                    "description": "Create interactive visualizations and reports",
                    "expected_output": "Professional charts and dashboards"
                }
            ],
            "web": [
                {
                    "step": 1,
                    "action": "Target Analysis",
                    "tool": "url_analyzer",
                    "description": "Analyze target website structure and content",
                    "expected_output": "Website structure map and extraction strategy"
                },
                {
                    "step": 2,
                    "action": "Data Extraction",
                    "tool": tools[0]["tool_name"] if tools else "web_scraper",
                    "description": "Extract data using intelligent scraping techniques",
                    "expected_output": "Raw extracted data in structured format"
                },
                {
                    "step": 3,
                    "action": "Data Processing",
                    "tool": tools[1]["tool_name"] if len(tools) > 1 else "data_processor",
                    "description": "Clean and structure the extracted data",
                    "expected_output": "Clean, structured dataset ready for use"
                }
            ],
            "ml": [
                {
                    "step": 1,
                    "action": "Data Preprocessing",
                    "tool": "data_preprocessor",
                    "description": "Clean and prepare data for machine learning",
                    "expected_output": "Preprocessed training and test datasets"
                },
                {
                    "step": 2,
                    "action": "Model Training",
                    "tool": tools[0]["tool_name"] if tools else "ml_trainer",
                    "description": "Train and optimize the machine learning model",
                    "expected_output": "Trained model with performance metrics"
                },
                {
                    "step": 3,
                    "action": "Model Evaluation",
                    "tool": "model_evaluator",
                    "description": "Evaluate model performance and generate insights",
                    "expected_output": "Model performance report and recommendations"
                }
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
    
    @staticmethod
    async def generate_agent_response(query: str) -> Dict[str, Any]:
        """Generate a mock agent response"""
        
        # Simulate processing delay
        await asyncio.sleep(1)
        
        tools = MockMCPResponse.get_mock_tools(query)
        workflow = MockMCPResponse.get_mock_workflow(query, tools)
        
        response = {
            "agent_response": f"""
## 🤖 Dynamic Tool Retriever Analysis

I've analyzed your request: "{query}"

**Task Decomposition:**
- Identified {len(tools)} relevant tools from our 14,000+ tool database
- Generated a {len(workflow)}-step workflow for optimal execution
- Used vector similarity search to match tools to your specific needs

**MCP Integration Status:**
✅ Connected to Dynamic Tool Retriever MCP
✅ Neo4j vector database query completed
✅ Tool scoring and ranking complete
✅ Workflow generation successful

**Next Steps:**
The workflow below shows the recommended execution order. Each tool has been selected based on compatibility and performance metrics.
            """.strip(),
            
            "tools_retrieved": tools,
            "workflow_generated": workflow,
            "mcp_logs": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "MCP_QUERY",
                    "details": f"Queried Neo4j database with embedding for: '{query}'"
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "TOOL_RETRIEVAL",
                    "details": f"Found {len(tools)} matching tools with scores > 0.8"
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "WORKFLOW_GENERATION",
                    "details": f"Generated {len(workflow)}-step workflow based on tool capabilities"
                }
            ]
        }
        
        return response

class MockA2AClient:
    """Mock A2A client for testing"""
    
    def __init__(self):
        self.connected = True
    
    async def send_message_streaming(self, request):
        """Mock streaming message sending"""
        query = request.params.message['parts'][0]['text']
        
        # Simulate agent processing
        yield {
            "type": "status",
            "content": "🔄 Analyzing query and decomposing task...",
            "timestamp": datetime.now().isoformat()
        }
        
        await asyncio.sleep(0.5)
        
        yield {
            "type": "status", 
            "content": "🔍 Querying Dynamic Tool Retriever MCP...",
            "timestamp": datetime.now().isoformat()
        }
        
        await asyncio.sleep(0.5)
        
        yield {
            "type": "status",
            "content": "⚡ Performing vector similarity search on 14,000+ tools...",
            "timestamp": datetime.now().isoformat()
        }
        
        await asyncio.sleep(1)
        
        # Generate final response
        response = await MockMCPResponse.generate_agent_response(query)
        
        yield {
            "type": "agent_response",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
