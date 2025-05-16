from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from Utils.get_MCP_config import extract_config_from_github

model = LiteLlm(model="bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0")
root_agent = Agent(
    model=model,
    name='MCP_congif_agent',
    description='Agent to configure the MCP server',
    instruction='Based on the githubb url of the tools, find MCP server configuration and provide the configuration in json format',
    tools=[extract_config_from_github]
)
