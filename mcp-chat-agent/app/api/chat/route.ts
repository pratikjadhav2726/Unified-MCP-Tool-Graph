import { NextRequest } from "next/server"
import { Client } from "@modelcontextprotocol/sdk/client/index.js"
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js"
import { z } from "zod"
import fs from "fs/promises"
import path from "path"

export const maxDuration = 30

// Helper: Call Dynamic Tool Retriever MCP
async function getRelevantTools(userQuery: string) {
  const response = await fetch("http://localhost:8001/tool", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_description: userQuery, top_k: 5 }),
  })
  if (!response.ok) throw new Error("Failed to call Dynamic Tool Retriever MCP")
  return await response.json() // Array of tool info (see retriever README)
}

// Helper: Ensure a server is running via MCP Server Manager
async function ensureServerRunning(name: string, config: any) {
  const response = await fetch("http://localhost:9001/add_server", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, config }),
  })
  if (!response.ok) throw new Error(`Failed to add server ${name}`)
  return await response.json()
}

// Helper: Load latest MCP client config (with SSE endpoints)
async function loadClientConfig() {
  const configPath = path.resolve("/workspace/MCP_Server_Manager/mcp_client_config.json")
  const raw = await fs.readFile(configPath, "utf-8")
  return JSON.parse(raw)
}

// Helper: Connect to MCP server and call tool
async function callMcpTool(serverUrl: string, toolName: string, args: any) {
  const client = new Client({ name: "mcp-chat-agent", version: "1.0.0" })
  const transport = new StreamableHTTPClientTransport(new URL(serverUrl))
  await client.connect(transport)
  // List tools (optional, for validation)
  // const tools = await client.listTools()
  // Call the tool
  const result = await client.callTool({ name: toolName, arguments: args })
  await client.close()
  return result
}

export async function POST(req: NextRequest) {
  const { messages } = await req.json()
  const userMessage = messages[messages.length - 1]?.content || ""

  // 1. Discover relevant tools and their server configs
  const tools = await getRelevantTools(userMessage)

  // 2. Ensure all required servers are running
  for (const tool of tools) {
    if (tool.mcp_server_config && tool.mcp_server_config.mcpServers) {
      for (const [name, config] of Object.entries(tool.mcp_server_config.mcpServers)) {
        await ensureServerRunning(name, config)
      }
    }
  }

  // 3. Load latest client config for SSE endpoints
  const clientConfig = await loadClientConfig()

  // 4. For each tool, connect and call via MCP SDK
  //    (For demo, just call the top tool. Extend as needed for multi-tool workflows)
  const topTool = tools[0]
  let toolResult = null
  if (topTool && topTool.mcp_server_config && topTool.mcp_server_config.mcpServers) {
    const [serverName] = Object.keys(topTool.mcp_server_config.mcpServers)
    const serverInfo = clientConfig.mcpServers[serverName]
    if (!serverInfo) throw new Error(`No client config for server ${serverName}`)
    toolResult = await callMcpTool(serverInfo.url, topTool.tool_name, {}) // TODO: Map user args
  }

  // 5. Stream the result back (for now, just return as JSON)
  return new Response(JSON.stringify({ result: toolResult }), {
    headers: { "Content-Type": "application/json" },
  })
}
