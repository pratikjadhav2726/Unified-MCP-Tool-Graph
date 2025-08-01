# Unified MCP Tool Graph: A Intelligence Layer for Dynamic Tool Retrieval

 ![image](https://github.com/user-attachments/assets/31dedcf0-b66b-49df-95d6-69e36a9115f9)





**Unified MCP Tool Graph** is a research-driven project that aggregates and structures tool APIs from diverse **Model Context Protocol (MCP) servers** into a centralized **Neo4j graph database**. This graph functions as an intelligent infrastructure layer that enables **large language models (LLMs)** and **agentic AI systems** to **dynamically retrieve** the most relevant tools for any task — without being overwhelmed by redundant or confusing options.

---

## 🚀 Recent Updates: Dynamic MCP Server Spin-Up & Minimal Tool Context

### 🟢 Dynamic MCP Server Orchestration
- The system now **spins up only the MCP servers required for a given user query**. Five popular MCP servers (including the Dynamic Tool Retriever MCP) are kept warm by default; others are started on demand and kept alive for 10 minutes after last use.
- **Dynamic Tool Retriever MCP** returns not just tool metadata, but also the config needed to run/connect to the MCP server for each tool (fetched from the vendor's GitHub README automatically).
- **Automatic MCP Config Extraction:** Uses the vendor's GitHub repo to extract the MCP server config (from README) for each tool, so agents can spin up/connect to the right server on the fly.
- **Error Handling:** If config extraction fails, the system logs a warning and continues, ensuring robust tool retrieval.

### 🟢 Minimal Tool Context for LLMs/Agents
- **Only the exact tools required for the user query are loaded into the agent's context** (not all tools from all MCP servers). This prevents LLM confusion and infinite tool loops.
- **End-to-End Flow:**
    1. User query is received.
    2. Dynamic Tool Retriever MCP queries the Neo4j graph and returns the top relevant tools **plus their MCP server configs**.
    3. The agent spins up/connects to only the required MCP servers (using the configs), and loads only the retrieved tools.
    4. The agent executes the workflow and returns the answer.

### 🟢 A2A and LangGraph Agent Support
- **A2A Agent Example:** See `Example_Agents/A2A_DynamicToolAgent/` for a fully dynamic A2A agent that orchestrates MCP servers and tools per request.
- **LangGraph Example:** See `Example_Agents/Langgraph/` for a LangGraph agent using the same dynamic, minimal-tool approach.

---

> 🔬 This repository focuses on the creation and evolution of the **Unified Tool Graph Database**. Chatbot-based integration (e.g., LangChain) is treated as a modular extension of this foundational layer.

> 📢 Support for Cline, IDE's coming soon..

---

## Research Problem

As LLMs and autonomous agents evolve to interact with external tools and APIs, a critical bottleneck has emerged:

> **How can models efficiently select the right tool from an ever-expanding universe of APIs — without going into infinite loops or picking the wrong ones?**

### Why This Happens:
- **Tool Confusion:**  
  LLMs struggle when many tools offer similar functions (e.g., `create_post`, `schedule_post`, `post_to_social`), leading to indecision and incorrect tool calls.
  
- ↺ **Infinite Chains:**  
  Without a structured understanding of tool differences, LLMs often get stuck in unproductive chains, calling tools repetitively or selecting suboptimal ones.

- **Unstructured Access:**  
  Most current implementations dump all available tools into the LLM's context, overwhelming it with options and increasing hallucination risks.

---
<img width="1072" alt="image" src="https://github.com/user-attachments/assets/a3744678-8996-42e5-9ebc-8379d29ceedc" />

## ✅ Solution: The Unified MCP Tool Graph

This project proposes a structured, queryable solution: a **vendor-agnostic Neo4j graph database** of tools/APIs sourced from MCP servers (e.g., LinkedIn, Google, Facebook, Notion, etc.).

### 🔍 Key Capabilities:
- **Centralized Tool Intelligence:**  
  Store API descriptions, metadata, parameters, and inter-tool relationships in a graph format.

- **LLM-Friendly Query Layer:**  
  Agents can retrieve only the 3–4 most relevant tools per task using metadata and relationships, minimizing confusion.

- **Semantic Differentiation:**  
  Capture similarities and differences between tools using graph relationships (e.g., `overlaps_with`, `extends`, `preferred_for_task`) to guide decision-making.

---

## Modular Extensions

While the graph is the core, it enables powerful downstream use cases:

### Dynamic Tool Retrieval (DTR):
> A modular LangChain/Autogen chatbot extension that queries the graph and surfaces a minimal, accurate toolset for any given user intent.

This prevents LLMs from blindly scanning a massive tool library and instead gives them just what they need to complete the job — nothing more, nothing less.


**Key Implementation:**
- MCP servers are spun up on demand (using configs from the tool retriever MCP and GitHub), and shut down after inactivity.
- Only the 5 most popular MCPs are kept running at all times; others are ephemeral.
- Agents (A2A or LangGraph) only see the tools relevant to the current query, not the full universe of tools.

---

## Core Objectives

| Goal | Description |
|------|-------------|
| **Tool Ingestion** | Fetch APIs and schemas from public/private MCP servers and normalize them |
| **Tool Relationship Mapping** | Define graph edges like `overlaps_with`, `requires_auth`, `preferred_for`, `belongs_to_vendor` |
| **LLM-Oriented Queries** | Return task-specific tool bundles in real time |
| **Scalable Ecosystem** | Continuously add vendors and tools without retraining or hardcoding |
| **Agent-Aware Structure** | Guide LLM reasoning with metadata-rich, searchable tool representations |

---

## Key Advantages

- **Reduces Tool Confusion in LLMs**  
  Prevents tool overload by showing only task-relevant options. Avoids infinite call loops and incorrect tool selections.

- **Vendor-Agnostic Integration**  
  Unifies APIs from different providers into a single intelligent system.

- **Maps Interoperability**  
  Captures how tools relate or depend on each other, useful for chaining APIs in workflows.

- **Optimized Agentic Reasoning**  
  Empowers LLMs to reason efficiently with fewer distractions in the context window.

- **Scalable & Modular**  
  Can be updated independently of LLM or chatbot infrastructure. Extendable across any agent stack.

---

## Example Use Cases

- **"I want to schedule a post on LinkedIn and share it in Slack."**  
  → Graph returns only the relevant `create_post`, `schedule_post`, and `send_message` tools.

- **Custom AI Assistants for Enterprises:**  
  Only expose internal tools from the graph, filtered by access, scope, or function.

- **Smart Recommender Agents:**  
  Suggest best-matched tools based on tags, popularity, success rate, or dependencies.

**Integrations with LangGraph and A2A are available in the `Example_Agents` directory for streamlined agent workflows and dynamic tool orchestration.**

---

## 🛠️ How It Works (Summary)

1. **User submits a query** (e.g., "Schedule a LinkedIn post and share it in Slack.")
2. **Dynamic Tool Retriever MCP** queries the Neo4j graph and returns the most relevant tools **plus their MCP server configs** (fetched from GitHub if needed).
3. **MCP Server Manager** spins up/connects to only the required MCP servers (using the configs), and keeps them alive for 10 minutes after last use.
4. **Agent** (A2A or LangGraph) loads only the retrieved tools and executes the workflow.
5. **Result** is returned to the user, with minimal tool confusion and maximum efficiency.

---
---

## Coming Soon

- **Graph Ingestion Scripts**
- **Schema Blueprint + Cypher Queries**
- **Tool Visualization Playground**
- **LangChain DTR Chatbot Plug-in**
- **How-to Tutorials & Use Cases**

---

## Getting Started

```bash
git clone https://github.com/your-username/unified-mcp-tool-graph.git
cd unified-mcp-tool-graph
# Coming soon: ingestion pipeline, schema docs, and sample queries
```

---

## Contributing

If you’re passionate about agentic AI, graph databases, or LLM integration — we’d love your help!

- Submit ideas or vendor sources
- Open PRs for schema/design improvements
- Star the repo to support this research

---

## License

MIT License — free for academic, personal, and commercial use.

---

## Summary

Instead of dumping 100+ tools into a model’s prompt and expecting it to choose wisely, the **Unified MCP Tool Graph** equips your LLM with structure, clarity, and relevance.

It **fixes tool confusion**, **prevents infinite loops**, and enables **modular, intelligent agent workflows**.

Let’s build smarter systems — one tool graph at a time.

---

**Star the repo to follow the journey and make tools truly *intelligent, searchable, and modular*.**

## Updates on Development
#### Clustering on multi label open-ended usecases.

<img width="1072" alt="image" src="https://github.com/user-attachments/assets/a3744678-8996-42e5-9ebc-8379d29ceedc" />

****Created a GraphDB with Vendor and tools with embedings for vector search.
Need a way to categorize vendors and connect vendors with same category. eg( Web Search, File System, Social Media etc.)
No of Tools Supported 11066
No of MCP Servers(Official + Community) 4161****

![UnifiedMCPToolGraph](https://github.com/user-attachments/assets/1ac65df1-3c0d-44a8-96c4-efc0b1352b6c)



#### Query = I want to post a linkedIn post about the latest trends in AI.
```
Here are the top 5 tools recommended based on your task of creating a LinkedIn post about AI trends, along with brief explanations to help you choose:

---

### 1. **linkedin_post_generator** (Likely the Most Relevant)  
**Description**: Generates optimized LinkedIn posts with engaging headlines, content structure, and hashtags tailored for professional audiences.  
**Why Use**: Directly creates polished posts while suggesting multimedia (images, videos) and tone adjustments for maximum engagement.  

---

### 2. **ai_search** (Top Search Tool)  
**Vendor**: Higress AI-Search  
**Key Feature**: Aggregates **real-time data** from Google/Bing/Quark and academic sources like ArXiv for cutting-edge AI research and industry trends.  
**How to Use**:  
   - Query: `Latest AI trends 2024` → Get recent news, research papers, and opinion pieces.  
   - Useful for ensuring your post cites fresh, credible sources.  

---

### 3. **tavily-search** (Comprehensive Web Research)  
**Vendor**: Tavily  
**Key Feature**: AI-powered search with advanced filters (e.g., `time_range`, `exclude_domains`) to curate content from trusted sources.  
**How to Use**:  
   - Example: Search for "recent AI breakthroughs 2024" → Pull articles from tech blogs, IEEE, or MIT Tech Review to highlight in your post.  

---

### 4. **query_repository** (If Curating Open-Source or GitHub Content)  
**Vendor**: GitHub Chat  
**Use Case**:  
   - If your post references open-source projects (e.g., "Top AI tools from GitHub 2024"), use this to query repositories for trending AI-related code/repos.  

---

### 5. **social_media_analytics** (Post-Creation Optimization)  
**Use Case**:  
   - After drafting your post, analyze engagement metrics (e.g., "Which AI topics are trending this week?") to refine your draft based on what performs well on LinkedIn.  

---

### Recommended Workflow:  
1. **Research** using **ai_search** or **tavily-search** to gather the latest AI news and data (e.g., LLM progress, ethical AI debates).  
2. **Craft the Post** with **linkedin_post_generator** to ensure professional formatting and engagement hooks.  
3. **Validate** with quick checks via **query_repository** (if citing open-source tools) or **social_media_analytics** for topic popularity.  

Let me know if you'd like step-by-step instructions for any specific tool!
```

## MCP Server Proxying with mcp-proxy

This project uses [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) to expose stdio-based MCP servers as HTTP endpoints. `mcp-proxy` acts as a bridge between stdio MCP servers and HTTP clients, supporting both Streamable HTTP and SSE transports.

### How it works
- MCP servers are launched as subprocesses (stdio) and registered with `mcp-proxy`.
- Each server is exposed at:
  - `http://localhost:<port>/servers/<name>/` (Streamable HTTP, POST)
  - `http://localhost:<port>/servers/<name>/sse` (SSE, GET)
- The official MCP Python SDK can connect to the `/sse` endpoint using `sse_client`:

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import asyncio

async def main():
    mcp_url = "http://localhost:9000/servers/time/sse"
    async with sse_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # ... interact with the server ...

if __name__ == "__main__":
    asyncio.run(main())
```

See the [mcp-proxy documentation](https://github.com/sparfenyuk/mcp-proxy) for more details on configuration and advanced usage.


