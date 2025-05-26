"""
Provides a client for interacting with Agent-to-Agent (A2A) or
Model Context Protocol (MCP) compliant servers.

This module defines the `A2AClient` class, which facilitates sending various
task-related requests (e.g., send task, get task, cancel task) and handling
both standard JSON-RPC responses and Server-Sent Event (SSE) streams for
real-time updates.
"""
import json

from collections.abc import AsyncIterable
from typing import Any

import httpx

from httpx._types import TimeoutTypes
from httpx_sse import connect_sse

from common.types import (
    A2AClientHTTPError,
    A2AClientJSONError,
    AgentCard,
    CancelTaskRequest,
    CancelTaskResponse,
    GetTaskPushNotificationRequest,
    GetTaskPushNotificationResponse,
    GetTaskRequest,
    GetTaskResponse,
    JSONRPCRequest,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    SetTaskPushNotificationRequest,
    SetTaskPushNotificationResponse,
)


class A2AClient:
    """
    A client for interacting with an Agent-to-Agent (A2A) server.

    This client handles sending JSON-RPC requests for various operations like
    sending tasks, getting task status, canceling tasks, and managing
    push notification callbacks. It supports both standard request/response
    patterns and Server-Sent Events (SSE) for streaming task updates.
    """
    def __init__(
        self,
        agent_card: AgentCard | None = None,
        url: str | None = None,
        timeout: TimeoutTypes = 60.0,
    ):
        """
        Initializes the A2AClient.

        The client needs a target URL, which can be provided directly or
        extracted from an `AgentCard`.

        Args:
            agent_card: An optional `AgentCard` instance. If provided, its `url`
                        attribute is used as the target URL for the client.
            url: The target URL of the A2A server. This is used if `agent_card`
                 is not provided.
            timeout: The timeout for HTTP requests, in seconds. Defaults to 60.0.

        Raises:
            ValueError: If neither `agent_card` nor `url` is provided.
        """
        if agent_card and agent_card.url:
            self.url: str = agent_card.url
        elif url:
            self.url: str = url
        else:
            raise ValueError('Must provide either agent_card or url')
        self.timeout: TimeoutTypes = timeout

    async def _send_request(self, request: JSONRPCRequest) -> dict[str, Any]:
        """
        Sends a JSON-RPC request to the server and returns the JSON response.

        This is a helper method used by other public methods for standard
        request-response interactions.

        Args:
            request: The `JSONRPCRequest` (or a subclass) to send.
                     The request object is serialized to JSON before sending.

        Returns:
            A dictionary representing the JSON response from the server.

        Raises:
            A2AClientHTTPError: If an HTTP error occurs (e.g., server error,
                                  bad request indicated by status code).
            A2AClientJSONError: If the server's response is not valid JSON.
        """
        async with httpx.AsyncClient() as client:
            try:
                # Image generation or other long tasks might require a longer timeout.
                response = await client.post(
                    self.url, json=request.model_dump(), timeout=self.timeout
                )
                response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx
                return response.json()
            except httpx.HTTPStatusError as e:
                raise A2AClientHTTPError(e.response.status_code, str(e)) from e
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(f"Failed to decode JSON response: {e}") from e
            except httpx.RequestError as e: # Catch other httpx errors like network issues
                raise A2AClientHTTPError(400, f"HTTP request failed: {e}") from e


    async def send_task(self, payload: dict[str, Any]) -> SendTaskResponse:
        """
        Sends a task to the A2A server (non-streaming).

        Args:
            payload: A dictionary containing the parameters for the task,
                     as defined by the `TaskSendParams` model (though passed
                     as a dict here which then forms `SendTaskRequest.params`).
                     Typically includes `id`, `message`, `sessionId`, etc.

        Returns:
            A `SendTaskResponse` object parsed from the server's JSON response.
        """
        request = SendTaskRequest(params=payload) # type: ignore
        # The server is expected to return a JSON object that matches SendTaskResponse structure
        return SendTaskResponse(**await self._send_request(request))

    async def send_task_streaming(
        self, payload: dict[str, Any]
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """
        Sends a task to the A2A server and subscribes to Server-Sent Events (SSE)
        for real-time updates.

        Args:
            payload: A dictionary containing the parameters for the streaming task,
                     as defined by `TaskSendParams` (passed as a dict).

        Yields:
            `SendTaskStreamingResponse` objects parsed from the JSON data of
            each Server-Sent Event received from the server.

        Raises:
            A2AClientJSONError: If an SSE event's data is not valid JSON.
            A2AClientHTTPError: If there's an underlying HTTP request error during
                                SSE connection or streaming (e.g., network issue).
        """
        request = SendTaskStreamingRequest(params=payload) # type: ignore
        # Using httpx.Client (sync) here for connect_sse, as httpx_sse might not
        # fully support async client usage in all its examples or typical patterns.
        # If an async version of connect_sse compatible with AsyncClient is available
        # and preferred, this could be updated. For now, assuming sync client for SSE setup.
        # Timeout for SSE is often handled differently (e.g., infinite until stream ends or error).
        # `httpx.Client(timeout=None)` reflects this.
        with httpx.Client(timeout=None) as client: # Ensure this is appropriate for async context
            with connect_sse(
                client, 'POST', self.url, json=request.model_dump()
            ) as event_source:
                try:
                    for sse in event_source.iter_sse():
                        yield SendTaskStreamingResponse(**json.loads(sse.data))
                except json.JSONDecodeError as e:
                    raise A2AClientJSONError(f"Failed to decode SSE data: {e}") from e
                except httpx.RequestError as e: # Handles errors during SSE streaming
                    raise A2AClientHTTPError(400, f"SSE request error: {e}") from e

    async def get_task(self, payload: dict[str, Any]) -> GetTaskResponse:
        """
        Retrieves the current status and details of a specific task.

        Args:
            payload: A dictionary containing parameters to identify the task,
                     typically including the `id` of the task. Corresponds to
                     `TaskIdParams`.

        Returns:
            A `GetTaskResponse` object with the task's details.
        """
        request = GetTaskRequest(params=payload) # type: ignore
        return GetTaskResponse(**await self._send_request(request))

    async def cancel_task(self, payload: dict[str, Any]) -> CancelTaskResponse:
        """
        Requests the cancellation of an ongoing task.

        Args:
            payload: A dictionary containing parameters to identify the task
                     to be canceled, typically the task `id`. Corresponds to
                     `TaskIdParams`.

        Returns:
            A `CancelTaskResponse` object, usually indicating the result of
            the cancellation request.
        """
        request = CancelTaskRequest(params=payload) # type: ignore
        return CancelTaskResponse(**await self._send_request(request))

    async def set_task_callback( # Original name, maps to SetTaskPushNotification
        self, payload: dict[str, Any]
    ) -> SetTaskPushNotificationResponse:
        """
        Sets or updates the push notification callback configuration for a task.

        Args:
            payload: A dictionary containing parameters for the push notification,
                     such as the task `id` and `pushNotification` configuration
                     (URL, etc.). Corresponds to `TaskPushNotificationParams`.

        Returns:
            A `SetTaskPushNotificationResponse` object, typically confirming
            the setup.
        """
        request = SetTaskPushNotificationRequest(params=payload) # type: ignore
        return SetTaskPushNotificationResponse(
            **await self._send_request(request)
        )

    async def get_task_callback( # Original name, maps to GetTaskPushNotification
        self, payload: dict[str, Any]
    ) -> GetTaskPushNotificationResponse:
        """
        Retrieves the current push notification callback configuration for a task.

        Args:
            payload: A dictionary containing parameters to identify the task,
                     typically the task `id`. Corresponds to `TaskIdParams`.

        Returns:
            A `GetTaskPushNotificationResponse` object with the callback details.
        """
        request = GetTaskPushNotificationRequest(params=payload) # type: ignore
        return GetTaskPushNotificationResponse(
            **await self._send_request(request)
        )
