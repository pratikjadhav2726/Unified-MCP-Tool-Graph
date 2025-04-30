import re
import aiohttp
import json
import asyncio

async def fetch_github_page(url):
    """Fetch the content of a GitHub page."""
    if not url.endswith("/"):
        url += "/"

    # Default branch if not specified
    branch = "main"

    # Parse user, repo, and optional branch
    parts = url.split("/")
    user = parts[3]
    repo = parts[4]
    
    if "tree" in parts:
        branch = parts[6]

    # Construct raw URL to README.md
    url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/README.md"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Failed to fetch GitHub page: {url}")
            return await response.text()

async def extract_config_from_github(url):
    """Extract MCP server or installation config using regex."""
    content = await fetch_github_page(url)
    config_match = re.search(r'(```json\s*({\s*"mcpServers".*?})\s*```)', content, re.DOTALL)
    if config_match:
        try:
            raw_config = config_match.group(1)  # Get the matched string
            config_match = re.sub(r'\s+', ' ', raw_config).strip()
            config_match = config_match.strip('```json').strip('```').strip()
            cleaned_json_string = re.sub(r',\s*([}\]])', r'\1', config_match)
            config_match = json.loads(cleaned_json_string)
            return (config_match)
        except json.JSONDecodeError:
            raise ValueError("Failed to decode JSON from GitHub content.")
    raise ValueError("No valid configuration found in GitHub content.")

async def main():
    url = "https://github.com/awslabs/mcp/tree/main/src/aws-documentation-mcp-server"
    config = await extract_config_from_github(url)
    print(json.dumps(config,indent=4))  # Pretty-print the configuration

# Run the async main function
asyncio.run(main())