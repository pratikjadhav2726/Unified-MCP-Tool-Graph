import re
import aiohttp
import json
import asyncio
import os
import dotenv
dotenv.load_dotenv()  # Load environment variables from .env file

async def fetch_github_page_async(url):
    """
    Fetch the content of a GitHub page's README.md asynchronously.
    Args:
        url (str): The GitHub repository URL.
    Returns:
        str: The content of the README.md file.
    Raises:
        ValueError: If the URL is invalid.
        Exception: If the README cannot be fetched.
    """
    if not url.endswith("/"):
        url += "/"

    branch = "main"
    parts = url.split("/")
    try:
        user = parts[3]
        repo = parts[4]
    except IndexError:
        raise ValueError(f"Invalid GitHub URL: {url}")

    subdir = ""
    if "tree" in parts:
        try:
            branch = parts[6]
            subdir = "/".join(parts[7:-1]) if parts[-1] == '' else "/".join(parts[7:])
        except IndexError:
            branch = "main"
            subdir = ""

    if subdir:
        raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{subdir}/README.md"
    else:
        raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/README.md"
    try:
        timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(raw_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch GitHub page: {raw_url} (status {response.status})")
                return await response.text()
    except Exception as e:
        # Log and re-raise for upstream error handling
        print(f"[ERROR] Error fetching GitHub README: {e}")
        raise Exception(f"Error fetching GitHub README: {e}")


async def extract_config_from_github_async(url):
    """
    Extract MCP server or installation config using regex from a GitHub repo's README.md asynchronously.
    Args:
        url (str): The GitHub repository URL.
    Returns:
        dict: The parsed MCP server config if found.
    Raises:
        Exception: If the README cannot be fetched or config cannot be parsed.
    """
    try:
        content = await fetch_github_page_async(url)
    except Exception as e:
        print(f"[ERROR] Failed to fetch README for config extraction: {e}")
        raise Exception(f"Failed to fetch README for config extraction: {e}")

    matches = re.finditer(r'```json\s*({\s*"mcpServers".*?})\s*```', content, re.DOTALL)
    for match in matches:
        try:
            raw_config = match.group(1)
            config_str = re.sub(r'\s+', ' ', raw_config).strip()
            cleaned_json_string = re.sub(r',\s*([}\]])', r'\1', config_str)
            

            config = json.loads(cleaned_json_string)
            print("DEBUG: Raw config parsed from README:", json.dumps(config, indent=2))

            if "mcpServers" in config and isinstance(config["mcpServers"], dict):
                filtered_servers = {
                    name: server
                    for name, server in config["mcpServers"].items()
                    if server.get("command") in ("npx", "python")
                }
                if filtered_servers:
                    result = {"mcpServers": filtered_servers}
                    result = inject_env_keys(result)
                    return result
        except Exception as e:
            print(f"[ERROR] Failed to process a config block: {e}")

    print(f"[WARN] No valid configuration found in GitHub content for {url}")
    raise ValueError("No valid configuration found in GitHub content.")


def inject_env_keys(mcp_config):
    """
    Inject environment variable values into the MCP config dictionary.
    Args:
        mcp_config (dict): The MCP config dictionary.
    Returns:
        dict: The MCP config with environment variables injected.
    """
    if not isinstance(mcp_config, dict):
        print("[ERROR] MCP config is not a dictionary.")
        return mcp_config
    mcp_servers = mcp_config.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        print("[ERROR] 'mcpServers' is not a dictionary in MCP config.")
        return mcp_config
    for server, cfg in mcp_servers.items():
        if not isinstance(cfg, dict):
            print(f"[WARN] Config for server '{server}' is not a dictionary.")
            continue
        env_dict = cfg.get("env", {})
        if not isinstance(env_dict, dict):
            print(f"[WARN] 'env' for server '{server}' is not a dictionary.")
            continue
        for key in env_dict:
            env_val = os.getenv(key)
            if env_val:
                env_dict[key] = env_val
            else:
                print(f"[WARN] Environment variable '{key}' not found for server '{server}'. Using default or placeholder.")
    return mcp_config

# Example usage for testing
if __name__ == "__main__":
    async def main():
        """Test the config extraction utility with error handling."""
        url = "https://github.com/supabase-community/supabase-mcp"
        try:
            config = await extract_config_from_github_async(url)
            config = inject_env_keys(config)
            print(json.dumps(config, indent=4))
        except Exception as e:
            print(f"[TEST ERROR] {e}")
    asyncio.run(main())
