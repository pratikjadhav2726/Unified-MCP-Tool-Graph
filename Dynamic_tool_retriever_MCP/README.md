# Dynamic Tool Retriever MCP

This directory contains the core implementation of the Dynamic Tool Retriever using the Model Context Protocol (MCP). The system provides intelligent, context-aware tool discovery through semantic search and environment validation.

## 🚀 Overview

The Dynamic Tool Retriever MCP serves as the intelligence layer for the Unified MCP Tool Graph project, enabling:

- **Semantic Tool Discovery**: Uses local Sentence Transformers to find tools relevant to user queries
- **Environment Validation**: Automatically filters tools based on available API keys and configurations  
- **Dynamic MCP Integration**: Extracts and validates MCP server configurations from vendor repositories
- **Intelligent Ranking**: Combines similarity scores with practical availability for optimal tool selection

## 📁 Files

### Core Components

- **[`server.py`](server.py)**: Main MCP server implementation with the `dynamic_tool_retriever` tool
- **[`embedder.py`](embedder.py)**: Text embedding generation using local Sentence Transformers
- **[`neo4j_retriever.py`](neo4j_retriever.py)**: Neo4j graph database interaction and tool querying

### Key Features in `server.py`

- **Local Embeddings**: Uses Sentence Transformers (no API keys required for embeddings)
- **Async Configuration Fetching**: Parallel extraction of MCP configs from GitHub repositories
- **Environment Key Validation**: Automatic filtering based on available API keys in `.env`
- **Error Handling**: Robust fallback mechanisms for failed config extractions
- **Structured Responses**: Standardized tool information with complete MCP server configurations

## 🛠️ Installation & Setup

### Prerequisites

```bash
# Install required dependencies
pip install -r requirements.txt

# Ensure Neo4j is running with the tool graph database
# See main project README for Neo4j setup instructions
```

### Environment Configuration

Create a `.env` file in the project root with your API keys. **Note: No OpenAI API key is required** as this system uses local Sentence Transformers for embeddings:

```bash
# Example .env file (NO OpenAI API key needed!)
GITHUB_TOKEN=your_github_token           # Optional: for GitHub config extraction
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Add any API keys for tools you want to use
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
# etc...
```

## 🚀 Usage

### Running the MCP Server

```bash
# Start the Dynamic Tool Retriever MCP server
python Dynamic_tool_retriever_MCP/server.py
```

The server will start on the default SSE transport and be available for MCP client connections.

### Using the Tool

The server exposes one main tool: `dynamic_tool_retriever`

#### Input Parameters

```python
{
    "task_description": "I want to post a LinkedIn article about AI trends",
    "top_k": 5,                    # Optional: default 3, max 50
    "official_only": false         # Optional: default false
}
```

#### Response Format

```json
[
    {
        "tool_name": "linkedin_post_generator",
        "tool_description": "Creates optimized LinkedIn posts with engaging content",
        "tool_parameters": {...},
        "tool_required_parameters": [...],
        "vendor_name": "LinkedIn Tools Inc",
        "vendor_repo": "https://github.com/vendor/linkedin-tools",
        "similarity_score": 0.89,
        "mcp_server_config": {
            "mcpServers": {
                "linkedin-tools": {
                    "command": "python",
                    "args": ["server.py"],
                    "env": {
                        "LINKEDIN_API_KEY": "required"
                    }
                }
            }
        }
    }
]
```

## 🔧 MCP Server Configuration

### For Agent Integration

```json
{
    "mcpServers": {
        "dynamic-tool-retriever": {
            "name": "Dynamic Tool Retriever MCP",
            "description": "Retrieves relevant tools using semantic search over Neo4j graph",
            "command": "python",
            "args": ["Dynamic_tool_retriever_MCP/server.py"],
            "endpoint": "http://localhost:8001",
            "env": {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "your_password"
            }
        }
    }
}
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEO4J_URI` | Neo4j database connection URI | Yes |
| `NEO4J_USER` | Neo4j username | Yes |
| `NEO4J_PASSWORD` | Neo4j password | Yes |
| `GITHUB_TOKEN` | GitHub token for config extraction | Optional |

**Important**: Unlike many AI systems, this tool retriever **does NOT require an OpenAI API key** because it uses local Sentence Transformers for text embeddings.

## 🔍 How It Works

### 1. Local Semantic Search Pipeline

```
User Query → Local Sentence Transformers → Vector Search in Neo4j → Candidate Tools
```

The system uses the `sentence-transformers/all-MiniLM-L6-v2` model locally, which provides:
- **No API costs**: Runs entirely locally
- **Fast inference**: Optimized for speed and performance
- **Privacy**: No data sent to external services
- **Reliability**: No external dependencies or rate limits

### 2. Environment Validation

```
Candidate Tools → GitHub Config Extraction → Env Key Validation → Valid Tools
```

### 3. Intelligent Ranking

```
Valid Tools → Similarity Score Ranking → Top-K Selection → Final Response
```

### 4. Configuration Integration

Each returned tool includes:
- Complete MCP server configuration
- Required environment variables
- Installation/setup instructions
- Compatibility validation results

## 🎯 Integration Examples

### With A2A Agents

```python
# Example from A2A_DynamicToolAgent
tools = await dynamic_tool_retriever_client.call_tool(
    "dynamic_tool_retriever",
    {
        "task_description": user_query,
        "top_k": 5,
        "official_only": False
    }
)

# Use returned MCP configs to spin up required servers
for tool in tools:
    if tool["mcp_server_config"]:
        await mcp_manager.start_server(tool["mcp_server_config"])
```

### With LangGraph Agents

```python
# Example from LangGraph agent
retrieved_tools = await tool_retriever.retrieve_tools(
    task_description=state["user_query"],
    top_k=3
)

# Load only the retrieved tools into the agent context
agent_tools = [create_tool_from_config(tool) for tool in retrieved_tools]
```

## 📊 Performance & Monitoring

### Logging

The server provides detailed logging at multiple levels:

```python
# Enable debug logging for detailed trace
logging.basicConfig(level=logging.DEBUG)

# Monitor key operations
logger.info("Processing task: 'task_description'")
logger.info("Retrieved X initial candidate tools")
logger.info("Found Y tools with valid configurations") 
logger.info("Selected tools: [tool_names]")
```

### Metrics

- **Candidate Retrieval**: Initial tools from semantic search
- **Configuration Success Rate**: Tools with valid MCP configs
- **Environment Match Rate**: Tools with available API keys
- **Final Selection**: Top-k tools returned to agent

### Performance Benefits

Using local Sentence Transformers provides:
- **Zero latency**: No network calls for embeddings
- **Zero cost**: No API usage fees
- **High throughput**: Can process many queries simultaneously
- **Offline capability**: Works without internet connection

## 🔒 Security & Best Practices

### Environment Key Protection

- Never expose API keys in logs or responses
- Use `.env` files for local development
- Implement proper secret management in production

### Rate Limiting

- GitHub API calls are cached when possible
- Failed config extractions are logged but don't block retrieval
- Async operations prevent blocking on slow network calls

### Error Handling

- Graceful degradation when configs can't be fetched
- Fallback responses without MCP configurations
- Comprehensive logging for debugging

## 🚀 First-Time Setup

### 1. Install Dependencies

```bash
pip install sentence-transformers neo4j python-dotenv aiohttp pydantic
```

### 2. Start Neo4j

```bash
# Using Docker
docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

### 3. Configure Environment

```bash
# Create .env file
echo "NEO4J_URI=bolt://localhost:7687" > .env
echo "NEO4J_USER=neo4j" >> .env
echo "NEO4J_PASSWORD=password" >> .env
```

### 4. Run the Server

```bash
python Dynamic_tool_retriever_MCP/server.py
```

## 🤝 Contributing

When contributing to the Dynamic Tool Retriever MCP:

1. **Maintain Backward Compatibility**: Don't break existing tool interfaces
2. **Add Comprehensive Logging**: Help with debugging and monitoring
3. **Test Environment Validation**: Ensure proper API key filtering
4. **Document Configuration Changes**: Update this README for any new env vars

## 📚 Related Documentation

- **[Main Project README](../README.md)**: Overall project architecture
- **[A2A Agent Example](../Example_Agents/A2A_DynamicToolAgent/README.md)**: Integration with A2A protocol
- **[LangGraph Agent Example](../Example_Agents/Langgraph/README.md)**: Integration with LangGraph
- **[Ingestion Pipeline](../Ingestion_pipeline/README.md)**: How tools are added to the graph

## 🐛 Troubleshooting

### Common Issues

**No tools returned:**
- Check Neo4j connection and data
- Verify Sentence Transformers model downloads correctly
- Ensure `.env` file has required API keys for specific tools

**Config extraction fails:**
- Check GitHub token permissions (if using private repos)
- Verify repository URLs are accessible
- Review GitHub API rate limits

**Environment validation fails:**
- Confirm all required API keys are in `.env`
- Check key naming matches MCP config requirements
- Verify `.env` file is in the correct location

**Sentence Transformers model download issues:**
```bash
# Force download the model
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

### Model Information

The system uses `sentence-transformers/all-MiniLM-L6-v2`:
- **Size**: ~80MB
- **Dimensions**: 384
- **Languages**: English (primarily)
- **Performance**: Good balance of speed and quality
- **License**: Apache 2.0

---

*This Dynamic Tool Retriever MCP powers intelligent tool discovery for the entire Unified MCP Tool Graph ecosystem, using **local AI models** for privacy, speed, and cost-effectiveness - no external API keys required for core functionality!*
