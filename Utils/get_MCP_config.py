
import re
import aiohttp
import json
import asyncio

async def fetch_github_page_async(url):
    """Fetch the content of a GitHub page asynchronously."""
    if not url.endswith("/"):
        url += "/"

    branch = "main"
    parts = url.split("/")
    try:
        user = parts[3]
        repo = parts[4]
    except IndexError:
        raise ValueError(f"Invalid GitHub URL: {url}")

    if "tree" in parts:
        try:
            branch = parts[6]
        except IndexError:
            branch = "main"

    raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/README.md"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(raw_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch GitHub page: {raw_url} (status {response.status})")
                return await response.text()
    except Exception as e:
        raise Exception(f"Error fetching GitHub README: {e}")


async def extract_config_from_github_async(url):
    """Extract MCP server or installation config using regex from a GitHub repo's README.md asynchronously."""
    try:
        content = await fetch_github_page_async(url)
    except Exception as e:
        raise Exception(f"Failed to fetch README for config extraction: {e}")

    config_match = re.search(r'```json\s*({\s*"mcpServers".*?})\s*```', content, re.DOTALL)
    if config_match:
        try:
            raw_config = config_match.group(1)
            config_str = re.sub(r'\s+', ' ', raw_config).strip()
            cleaned_json_string = re.sub(r',\s*([}\]])', r'\1', config_str)
            config = json.loads(cleaned_json_string)
            return config
        except json.JSONDecodeError:
            raise ValueError("Failed to decode JSON from GitHub content.")
    raise ValueError("No valid configuration found in GitHub content.")


# Example usage for testing
# async def main():
#     url = "https://github.com/atla-ai/atla-mcp-server"
#     try:
#         config = await extract_config_from_github_async(url)
#         print(json.dumps(config, indent=4))
#     except Exception as e:
#         print(f"Error: {e}")
#
# if __name__ == "__main__":
#     asyncio.run(main())