import logging
import os
import httpx
import uvicorn
import click
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from .a2a_dynamic_tool_agent_executor import A2ADynamicToolAgentExecutor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=11000)
def main(host, port):
    """Starts the A2A Dynamic Tool Agent server."""
    try:
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id='a2a_dynamic_tool_agent',
            name='A2A Dynamic Tool Retrieval Agent',
            description='Agent that dynamically retrieves and uses tools from MCP servers.',
            tags=['dynamic tools', 'MCP', 'automation'],
            examples=['Find the best tool for data extraction.'],
        )
        agent_card = AgentCard(
            name='A2A Dynamic Tool Agent',
            description='Agent that decomposes tasks and retrieves the best tools to solve them.',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=['text', 'text/plain'],
            defaultOutputModes=['text', 'text/plain'],
            capabilities=capabilities,
            skills=[skill],
        )
        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=A2ADynamicToolAgentExecutor(),
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
