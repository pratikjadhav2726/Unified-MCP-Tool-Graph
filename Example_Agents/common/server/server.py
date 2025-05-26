"""
Provides an A2A (Agent-to-Agent) server implementation using Starlette.

This module defines the `A2AServer` class, which sets up a web server
to handle JSON-RPC requests directed at an agent. It integrates with a
`TaskManager` to process these requests and provides standard endpoints
for agent metadata (AgentCard) and task operations.
"""
import json
import logging

from collections.abc import AsyncIterable
from typing import Any

from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from common.server.task_manager import TaskManager
from common.types import (
    A2ARequest,
    AgentCard,
    CancelTaskRequest,
    GetTaskPushNotificationRequest,
    GetTaskRequest,
    InternalError,
    InvalidRequestError,
    JSONParseError,
    JSONRPCResponse,
    SendTaskRequest,
    SendTaskStreamingRequest,
    SetTaskPushNotificationRequest,
    TaskResubscriptionRequest,
)


logger = logging.getLogger(__name__)


class A2AServer:
    """
    An Agent-to-Agent (A2A) server built using Starlette.

    This server handles JSON-RPC requests for an agent, routing them to a
    provided `TaskManager` instance for processing. It exposes a main endpoint
    for task operations and a standard `/.well-known/agent.json` endpoint
    to serve the agent's `AgentCard` (metadata).
    """
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 5000,
        endpoint: str = '/',
        agent_card: AgentCard | None = None,
        task_manager: TaskManager | None = None,
    ):
        """
        Initializes the A2AServer.

        Args:
            host: The hostname or IP address to bind the server to.
            port: The port number for the server.
            endpoint: The path for the main JSON-RPC request processing endpoint.
            agent_card: An `AgentCard` instance containing metadata about the agent
                        served by this server. Required to start the server.
            task_manager: A `TaskManager` instance responsible for handling the
                          logic of different A2A requests (e.g., send_task, get_task).
                          Required to start the server.
        """
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.task_manager: TaskManager | None = task_manager
        self.agent_card: AgentCard | None = agent_card
        self.app = Starlette()
        self.app.add_route(
            self.endpoint, self._process_request, methods=['POST']
        )
        self.app.add_route(
            '/.well-known/agent.json', self._get_agent_card, methods=['GET']
        )

    def start(self):
        """
        Starts the A2A server using Uvicorn.

        Raises:
            ValueError: If `agent_card` or `task_manager` was not provided
                        during initialization.
        """
        if self.agent_card is None:
            raise ValueError('agent_card is not defined. It must be provided during server initialization.')

        if self.task_manager is None:
            # Corrected error message to refer to task_manager
            raise ValueError('task_manager is not defined. It must be provided during server initialization.')

        import uvicorn # Local import to avoid making uvicorn a hard dependency for other uses

        uvicorn.run(self.app, host=self.host, port=self.port)

    def _get_agent_card(self, request: Request) -> JSONResponse:
        """
        Handles GET requests to `/.well-known/agent.json`.

        Serves the `AgentCard` provided during server initialization as a JSON response.

        Args:
            request: The Starlette `Request` object (unused in this method but
                     required by Starlette route handlers).

        Returns:
            A `JSONResponse` containing the agent card data.
        """
        # Assuming self.agent_card is not None due to checks in start(),
        # but defensive coding might add another check or rely on Starlette's
        # error handling if accessed before start().
        return JSONResponse(self.agent_card.model_dump(exclude_none=True)) # type: ignore

    async def _process_request(self, request: Request) -> JSONResponse | EventSourceResponse:
        """
        Processes incoming JSON-RPC requests to the main agent endpoint.

        This method:
        1. Parses the JSON request body.
        2. Validates the request and determines its type (e.g., SendTask, GetTask)
           using `A2ARequest.validate_python`.
        3. Delegates handling to the appropriate method of the `task_manager`.
        4. Formats the result from the task manager into an HTTP response
           (either `JSONResponse` or `EventSourceResponse` for streaming).
        5. Catches exceptions and uses `_handle_exception` to return a
           standardized JSON-RPC error response.

        Args:
            request: The Starlette `Request` object.

        Returns:
            A `JSONResponse` for standard RPC calls or an `EventSourceResponse`
            for streaming RPC calls (like `send_task_streaming`).
        """
        # Ensure task_manager is available; this should be guaranteed if start() was called.
        if not self.task_manager:
            return self._handle_exception(ValueError("TaskManager not initialized"))

        try:
            body = await request.json()
            # A2ARequest.validate_python attempts to parse and identify the specific request type
            json_rpc_request = A2ARequest.validate_python(body)

            # Dispatch to the appropriate TaskManager method based on request type
            if isinstance(json_rpc_request, GetTaskRequest):
                result = await self.task_manager.on_get_task(json_rpc_request)
            elif isinstance(json_rpc_request, SendTaskRequest):
                result = await self.task_manager.on_send_task(json_rpc_request)
            elif isinstance(json_rpc_request, SendTaskStreamingRequest):
                result = await self.task_manager.on_send_task_subscribe(
                    json_rpc_request
                )
            elif isinstance(json_rpc_request, CancelTaskRequest):
                result = await self.task_manager.on_cancel_task(
                    json_rpc_request
                )
            elif isinstance(json_rpc_request, SetTaskPushNotificationRequest):
                result = await self.task_manager.on_set_task_push_notification(
                    json_rpc_request
                )
            elif isinstance(json_rpc_request, GetTaskPushNotificationRequest):
                result = await self.task_manager.on_get_task_push_notification(
                    json_rpc_request
                )
            elif isinstance(json_rpc_request, TaskResubscriptionRequest):
                result = await self.task_manager.on_resubscribe_to_task(
                    json_rpc_request
                )
            else:
                # This case should ideally be caught by A2ARequest.validate_python
                # or indicate a request type known by A2ARequest but not handled here.
                logger.warning(
                    f'Unexpected or unhandled request type: {type(json_rpc_request)}'
                )
                # Using specific error for unhandled known types might be better
                raise ValueError(f'Unexpected request type: {type(json_rpc_request)}')

            return self._create_response(result)

        except Exception as e: # Catch-all for parsing, validation, or task manager errors
            return self._handle_exception(e)

    def _handle_exception(self, e: Exception) -> JSONResponse:
        """
        Handles exceptions raised during request processing and creates a
        standardized JSON-RPC error response.

        - `json.decoder.JSONDecodeError` is mapped to `JSONParseError`.
        - Pydantic's `ValidationError` is mapped to `InvalidRequestError`,
          including validation details.
        - Other exceptions are mapped to a generic `InternalError`.

        Args:
            e: The exception that occurred.

        Returns:
            A `JSONResponse` containing the JSON-RPC error object, typically
            with a 400 status code.
        """
        if isinstance(e, json.decoder.JSONDecodeError):
            json_rpc_error = JSONParseError()
        elif isinstance(e, ValidationError):
            # Extract validation error details for a more informative response
            json_rpc_error = InvalidRequestError(data=json.loads(e.json())) # type: ignore
        else:
            logger.error(f'Unhandled exception during request processing: {e}', exc_info=True)
            json_rpc_error = InternalError() # type: ignore

        # All JSON-RPC errors (even internal ones) are typically part of a successful
        # HTTP response (e.g., 200 OK) unless the error is at the HTTP transport level.
        # However, the original code returns 400 for these. Adhering to that.
        response = JSONRPCResponse(id=None, error=json_rpc_error) # type: ignore
        return JSONResponse(
            response.model_dump(exclude_none=True), status_code=400
        )

    def _create_response(
        self, result: Any
    ) -> JSONResponse | EventSourceResponse:
        """
        Creates an appropriate HTTP response from the result of a TaskManager operation.

        - If the result is an `AsyncIterable`, it's treated as a stream for
          Server-Sent Events (SSE) and wrapped in an `EventSourceResponse`.
          Each item from the iterable is expected to be a Pydantic model that
          can be serialized to JSON.
        - If the result is a `JSONRPCResponse`, it's serialized to JSON and
          returned as a standard `JSONResponse`.
        - Other result types are considered unexpected and will raise a `ValueError`.

        Args:
            result: The result object returned by a `TaskManager` method.

        Returns:
            A `JSONResponse` for single responses or an `EventSourceResponse`
            for streaming responses.

        Raises:
            ValueError: If the `result` type is not `AsyncIterable` or
                        `JSONRPCResponse`.
        """
        if isinstance(result, AsyncIterable):
            # Define an async generator to format items from the result iterable
            # into SSE event data.
            async def event_generator(stream_result: AsyncIterable[Any]) -> AsyncIterable[dict[str, str]]:
                async for item in stream_result:
                    # Each item should be a Pydantic model (e.g., SendTaskStreamingResponse)
                    # that can be dumped to JSON.
                    yield {'data': item.model_dump_json(exclude_none=True)}

            return EventSourceResponse(event_generator(result))

        if isinstance(result, JSONRPCResponse):
            return JSONResponse(result.model_dump(exclude_none=True))

        # If the result is neither of the expected types, log an error and raise.
        logger.error(f'Unexpected result type from TaskManager: {type(result)}')
        raise ValueError(f'Unexpected result type from TaskManager: {type(result)}')
