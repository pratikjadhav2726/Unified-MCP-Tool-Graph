# Dynamic Tool Retriever MCP - Gradio Chatbot Demo

This folder contains a comprehensive Gradio-based chatbot demo that showcases the **Dynamic Tool Retriever MCP** system with your LangGraph A2A agent.

## 🚀 Features

### Core Functionality
- **Interactive Chat Interface** - Natural language task descriptions
- **Real-time Tool Retrieval** - Access to 14,000+ tools from 4,000+ MCP servers
- **AI-Generated Workflows** - Step-by-step execution plans
- **Live MCP Communication Logs** - See the system working behind the scenes
- **Vector Similarity Search** - Intelligent tool matching using Neo4j

### Demo Modes
- **Real Mode** - Connects to your actual LangGraph A2A agent
- **Mock Mode** - Fully functional demo mode when agent isn't running
- **Auto-Detection** - Automatically falls back to mock mode if agent unavailable

## 📁 Files Overview

```
gradio_demo/
├── enhanced_demo.py      # Main demo application with rich UI
├── chatbot_ui.py        # Basic chatbot implementation
├── mock_agent.py        # Mock A2A agent for testing
├── requirements.txt     # Python dependencies
├── start_demo.sh       # Easy startup script
└── README.md           # This file
```

## 🛠️ Setup & Installation

### Quick Start (Recommended)
```bash
cd /Users/pratik/Documents/Unified-MCP-Tool-Graph
./gradio_demo/start_demo.sh
```

The startup script will:
1. Create a virtual environment
2. Install dependencies
3. Check for your A2A agent
4. Start the demo in appropriate mode

### Manual Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r gradio_demo/requirements.txt

# Run the demo
python gradio_demo/enhanced_demo.py
```

## 🎯 Usage

### With Real A2A Agent
1. **Start your LangGraph A2A Agent:**
   ```bash
   python -m Example_Agents.Langgraph --host localhost --port 10000
   ```

2. **Start the demo:**
   ```bash
   python gradio_demo/enhanced_demo.py
   ```

3. **Open browser:** Navigate to `http://localhost:7860`

### Mock Mode (For Demonstration)
```bash
python gradio_demo/enhanced_demo.py --mock
```

This mode simulates the full MCP system functionality without requiring the actual agent to be running.

## 🎨 Demo Interface

### Main Components

1. **Metrics Dashboard**
   - Shows 14,000+ available tools
   - 4,000+ MCP servers
   - Performance metrics

2. **Chat Interface**
   - Natural language task input
   - Streaming responses
   - Clear conversation history

3. **Tools Panel**
   - Retrieved tools with similarity scores
   - Vendor information
   - Tool parameters and descriptions

4. **Workflow Panel**
   - AI-generated step-by-step plans
   - Tool coordination
   - Expected outputs

5. **MCP Logs Panel**
   - Real-time system operations
   - Neo4j database queries
   - Performance metrics

### Example Interactions

Try these example queries:
- "Create a complete data analysis pipeline for customer sales data"
- "Build a web scraping system for e-commerce product monitoring"
- "Set up a machine learning pipeline for sentiment analysis"
- "Design a CI/CD workflow for a Python web application"

## ⚙️ Configuration

### Command Line Options
```bash
python gradio_demo/enhanced_demo.py [OPTIONS]

Options:
  --agent-url TEXT     URL of LangGraph A2A agent [default: http://localhost:10000]
  --host TEXT          Host to bind demo to [default: 0.0.0.0] 
  --port INTEGER       Port to run demo on [default: 7860]
  --share              Create public Gradio link
  --mock               Force mock mode
```

### Environment Variables
The demo respects the same environment variables as your main system:
- `NEO4J_URI` - Neo4j database connection
- `NEO4J_USER` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password
- `GROQ_API_KEY` - Groq API key for LLM

## 🔧 Customization

### Adding New Mock Tools
Edit `mock_agent.py` to add more realistic tool examples:

```python
def get_mock_tools(query: str) -> List[Dict[str, Any]]:
    # Add your custom tool definitions here
    pass
```

### Styling the Interface
Modify the `custom_css` in `enhanced_demo.py` to change the appearance:

```python
custom_css = """
    .demo-container { 
        /* Your custom styles */ 
    }
"""
```

### Extending Functionality
- Add new panels by modifying the Gradio layout
- Integrate with additional MCP servers
- Add metrics and monitoring dashboards

## 🐛 Troubleshooting

### Common Issues

1. **"A2A libraries not available"**
   - This is normal if you don't have the A2A client installed
   - Demo will run in mock mode automatically

2. **"Failed to connect to agent"**
   - Ensure your LangGraph agent is running on the correct port
   - Check if the agent URL is correct
   - Demo will fall back to mock mode

3. **Port already in use**
   - Use a different port: `--port 7861`
   - Or kill the existing process

4. **Gradio installation issues**
   - Update pip: `pip install --upgrade pip`
   - Try: `pip install gradio --no-cache-dir`

### Debug Mode
Run with debug logging:
```bash
python gradio_demo/enhanced_demo.py --debug
```

## 📊 System Architecture

```
User Input → Gradio UI → A2A Client → LangGraph Agent → MCP System
                ↓                                           ↓
            Mock Agent ←←←← Fallback Mode ←←←← Neo4j + Tools
```

## 🚀 Production Deployment

For production deployment:

1. **Use a proper WSGI server:**
   ```bash
   pip install uvicorn
   uvicorn enhanced_demo:app --host 0.0.0.0 --port 80
   ```

2. **Enable HTTPS and authentication**
3. **Configure proper logging and monitoring**
4. **Set up load balancing for high traffic**

## 📝 Contributing

To contribute to this demo:

1. Fork the repository
2. Create your feature branch
3. Add your improvements
4. Test with both real and mock modes
5. Submit a pull request

## 📄 License

This demo is part of the Unified MCP Tool Graph project and follows the same license terms.

---

**🎉 Enjoy exploring the Dynamic Tool Retriever MCP system!**

For questions or support, please refer to the main project documentation or open an issue.
