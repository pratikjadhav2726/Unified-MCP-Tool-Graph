import logging
import os
import click
import uvicorn
from dotenv import load_dotenv
from a2a.types import AgentCapabilities, AgentSkill
from langgraph_server_utils import create_langgraph_agent_a2a_server
from agent import ReactAgent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--host', default='localhost', help='Server host')
@click.option('--port', default=10020, help='Server port')
@click.option('--config', 'config_path', default='Example_Agents/Langgraph/mcp_server_config.json', help='Path to MCP config JSON')
def main(host, port, config_path):
    """Starts the LangGraph MCP A2A Agent server."""
    try:
        skills = [
            AgentSkill(
                id='dynamic_tool_agent',
                name='Dynamic Tool Retrieval Agent',
                description='Agent that dynamically retrieves and uses tools from MCP servers.',
                tags=['dynamic tools', 'MCP', 'automation'],
                examples=['Find the best tool for data extraction.'],
            )
        ]
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        server = create_langgraph_agent_a2a_server(
            agent_class=ReactAgent,
            name='LangGraph MCP Agent',
            description='A2A-compatible LangGraph agent for MCP tool orchestration.',
            skills=skills,
            host=host,
            port=port,
            agent_name='LangGraph MCP Agent',
            capabilities=capabilities,
            input_modes=ReactAgent.SUPPORTED_CONTENT_TYPES,
            output_modes=ReactAgent.SUPPORTED_CONTENT_TYPES,
            version='1.0.0',
            agent_init_args=[config_path]
        )
        uvicorn.run(server.build(), host=host, port=port)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1)

if __name__ == '__main__':
    main()
