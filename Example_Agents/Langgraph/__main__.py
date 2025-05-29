"""
Main entry point for launching the LangGraph-based MCP (Model Context Protocol) Agent Server.

This script sets up a Click-based command-line interface to configure and run
an A2A (Agent-to-Agent) server. The server hosts the LangGraph `ReactAgent`,
manages tasks using `AgentTaskManager`, and exposes agent capabilities,
skills, and metadata through an `AgentCard`.

It also handles push notification setup, including JWKS endpoint for authentication.
Environment variables, particularly `GROQ_API_KEY`, are crucial for its operation.
"""
import logging
import os
import click
from .Agent import ReactAgent
from .task_manager import AgentTaskManager
from common.server import A2AServer
from common.types import AgentCapabilities, AgentCard, AgentSkill, MissingAPIKeyError
from common.utils.push_notification_auth import PushNotificationSenderAuth
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10000)
def main(host: str, port: int):
    """
    Sets up and starts the LangGraph MCP Agent A2A server.

    This function orchestrates the initialization of various components:
    - Checks for required API keys (e.g., GROQ_API_KEY).
    - Defines the agent's capabilities, skills, and metadata (AgentCard).
    - Configures push notification authentication (JWKS).
    - Instantiates the `ReactAgent` (the core LangGraph agent logic).
    - Instantiates the `AgentTaskManager` to handle agent tasks.
    - Initializes and starts the `A2AServer` to serve the agent.

    Args:
        host: The hostname or IP address to bind the server to.
              Defaults to 'localhost'.
        port: The port number to bind the server to.
              Defaults to 10000.

    Raises:
        MissingAPIKeyError: If the `GROQ_API_KEY` environment variable is not set.
        SystemExit: If any critical error occurs during startup, the script will exit.
    """
    try:
        if not os.getenv('GROQ_API_KEY'):
            raise MissingAPIKeyError('GROQ_API_KEY environment variable not set.')
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill( # type: ignore
            id='breakdown_task',
            name='Task Decomposition and Tool Suggestion',
            description='Decomposes user tasks and retrieves suitable tools.',
            tags=['task breakdown', 'tools'],
            examples=['How do I automate my workflow?'],
        )
        agent_card = AgentCard( # type: ignore
            name='LangGraph MCP Agent',
            description='Breaks down tasks and retrieves tools.',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=ReactAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=ReactAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        # TODO: Make the config path configurable or relative
        agent = ReactAgent("/Users/pratik/Documents/Unified-MCP-Tool-Graph/Example_Agents/Langgraph/mcp_server_config.json")
        agent.sync_initialize_client()
        server = A2AServer( # type: ignore
            agent_card=agent_card, # type: ignore
            task_manager=AgentTaskManager( # type: ignore
                agent=agent,
                notification_sender_auth=notification_sender_auth,
            ),
            host=host,
            port=port,
            endpoint='/jsonrpc'
        )
        server.app.add_route(
            '/.well-known/jwks.json',
            notification_sender_auth.handle_jwks_endpoint,
            methods=['GET'],
        )
        logger.info(f'Starting server on {host}:{port}')
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f'Error: {e}')
        exit(1) # Exits with status 1 on missing API key
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1) # Exits with status 1 on other startup errors

if __name__ == '__main__':
    main()