import logging
import os
import httpx
from typing import Type, List, Optional

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv

from generic_langgraph_executor import create_langgraph_executor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


def create_langgraph_agent_a2a_server(
    agent_class: type,
    name: str,
    description: str,
    skills: list,
    host: str,
    port: int,
    agent_name: str,
    capabilities,
    input_modes: list,
    output_modes: list,
    version: str,
    check_api_key: bool = False,
    api_key_env_var: str = "",
    agent_init_args=None,
    agent_init_kwargs=None
):
    """Create an A2A server for any LangGraph agent. All configuration must be provided by the caller."""
    try:
        if check_api_key and api_key_env_var and not os.getenv(api_key_env_var):
            raise MissingAPIKeyError(
                f'{api_key_env_var} environment variable not set.'
            )
        agent_card = AgentCard(
            name=name,
            description=description,
            url=f'http://{host}:{port}/',
            version=version,
            defaultInputModes=input_modes,
            defaultOutputModes=output_modes,
            capabilities=capabilities,
            skills=skills,
        )
        executor = create_langgraph_executor(
            agent_class,
            agent_name,
            agent_init_args=agent_init_args,
            agent_init_kwargs=agent_init_kwargs
        )
        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        logger.info(f"Created A2A server for {name} on {host}:{port}")
        return server
    except MissingAPIKeyError as e:
        logger.error(f'Error: {e}')
        raise
    except Exception as e:
        logger.error(f'An error occurred during server setup: {e}')
        raise


# Utility function to create multiple servers at once
def create_multiple_langgraph_servers(server_configs: List[dict]):
    """Create multiple LangGraph agent servers from configuration.
    
    Args:
        server_configs: List of dictionaries with server configuration
                       Each dict should have: agent_class, name, description, skills, host, port
        
    Returns:
        List of A2AStarletteApplication instances
    """
    servers = []
    
    for config in server_configs:
        server = create_langgraph_agent_a2a_server(**config)
        servers.append(server)
    
    return servers 