import logging
from typing import Any, Type

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GenericLangGraphExecutor(AgentExecutor):
    """Generic executor that can handle any LangGraph agent."""

    def __init__(self, agent_class: Type, agent_name: str, agent_init_args=None, agent_init_kwargs=None):
        """Initialize the executor with any LangGraph agent class.
        Args:
            agent_class: The LangGraph agent class to instantiate
            agent_name: Human-readable name for logging (must be a string)
            agent_init_args: Positional arguments for agent_class
            agent_init_kwargs: Keyword arguments for agent_class
        """
        self.agent_class = agent_class
        self.agent_name = agent_name
        self.agent_init_args = agent_init_args or []
        self.agent_init_kwargs = agent_init_kwargs or {}
        self.agent = None  # Lazy initialization
        
    def _get_agent(self):
        """Lazy initialization of the agent instance."""
        if self.agent is None:
            try:
                self.agent = self.agent_class(*self.agent_init_args, **self.agent_init_kwargs)
                logger.info(f"Initialized {self.agent_name}")
            except Exception as e:
                logger.error(f"Failed to initialize {self.agent_name}: {e}")
                raise ServerError(error=InternalError()) from e
        return self.agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the LangGraph agent workflow.
        
        This method handles the A2A protocol communication and delegates
        the actual processing to the LangGraph agent.
        """
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)
        
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        
        try:
            # Get the agent instance
            agent = self._get_agent()
            
            # Stream the LangGraph workflow
            async for item in agent.stream(query, task.contextId):
                is_task_complete = item.get('is_task_complete', False)
                require_user_input = item.get('require_user_input', False)
                content = item.get('content', 'Processing...')

                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break
                else:
                    # Task completed successfully
                    await updater.add_artifact(
                        [Part(root=TextPart(text=content))],
                        name=f'{self.agent_name.lower().replace(" ", "_")}_result',
                    )
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'Error in {self.agent_name} execution: {e}')
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        """Validate the incoming request.
        
        Override this method in subclasses if specific validation is needed.
        """
        return False

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Cancel the current task.
        
        Override this method if the agent supports cancellation.
        """
        raise ServerError(error=UnsupportedOperationError())


# Factory function for easy creation of executors
def create_langgraph_executor(agent_class: Type, agent_name: str, agent_init_args=None, agent_init_kwargs=None) -> GenericLangGraphExecutor:
    """Factory function to create a LangGraph executor for any agent.
    Args:
        agent_class: The LangGraph agent class
        agent_name: Name for the agent (required)
        agent_init_args: Positional arguments for agent_class
        agent_init_kwargs: Keyword arguments for agent_class
    Returns:
        Configured GenericLangGraphExecutor instance
    """
    return GenericLangGraphExecutor(agent_class, agent_name, agent_init_args, agent_init_kwargs) 