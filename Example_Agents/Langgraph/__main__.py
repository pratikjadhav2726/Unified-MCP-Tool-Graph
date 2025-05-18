# __main__.py
import logging
import os
import click
from .agent import ReactAgent
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
def main(host, port):
    try:
        if not os.getenv('GROQ_API_KEY'):
            raise MissingAPIKeyError('GROQ_API_KEY environment variable not set.')
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id='breakdown_task',
            name='Task Decomposition and Tool Suggestion',
            description='Decomposes user tasks and retrieves suitable tools.',
            tags=['task breakdown', 'tools'],
            examples=['How do I automate my workflow?'],
        )
        agent_card = AgentCard(
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
        agent = ReactAgent("/Users/pratik/Documents/Unified-MCP-Tool-Graph/Example_Agents/Langgraph/mcp_server_config.json")
        agent.sync_initialize_client()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(
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
        exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1)

if __name__ == '__main__':
    main()