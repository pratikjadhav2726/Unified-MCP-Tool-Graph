import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

async def main():
    # Change this URL to match your running server/endpoint
    mcp_url = "http://localhost:9000/mcp/sequential-thinking/"  # Update if needed
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"Connected to MCP server at {mcp_url}")
            tools_response = await session.list_tools()
            tools = getattr(tools_response, "tools", [])
            print(f"Found {len(tools)} tools:")
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")

if __name__ == "__main__":
    asyncio.run(main()) 