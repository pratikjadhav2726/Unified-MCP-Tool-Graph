import logging
import os

import click
import httpx
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from .agent import ReactAgent
from .agent_executor import DynamicToolAgentExecutor  
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10000)
@click.option('--config', 'config_path', default='Example_Agents/Langgraph/mcp_server_config.json', help='Path to MCP config JSON')
def main(host, port, config_path):
    """Starts the Dynamic Tool Agent server."""
    try:
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id='dynamic_tool_agent',
            name='Dynamic Tool Retrieval Agent',
            description='Agent that dynamically retrieves and uses tools from MCP servers.',
            tags=['dynamic tools', 'MCP', 'automation'],
            examples=['Find the best tool for data extraction.'],
        )
        agent_card = AgentCard(
            name='Dynamic Tool Agent',
            description='Agent that decomposes tasks and retrieves the best tools to solve them.',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=ReactAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=ReactAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=DynamicToolAgentExecutor(config_path),
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx_client),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        uvicorn.run(server.build(), host=host, port=port)

    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1)


if __name__ == '__main__':
    main()
