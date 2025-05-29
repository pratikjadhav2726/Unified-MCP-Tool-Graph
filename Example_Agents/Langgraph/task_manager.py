"""
Manages tasks for the LangGraph-based ReactAgent within an A2A (Agent-to-Agent) server environment.

This module defines `AgentTaskManager`, which extends `InMemoryTaskManager` to handle
the specifics of interacting with the `ReactAgent`. This includes processing
incoming task requests (both synchronous and streaming), validating them, invoking
the agent, updating task states, managing artifacts, and handling push notifications
for task updates.
"""
import asyncio
import logging
import traceback
from collections.abc import AsyncIterable

from .Agent import ReactAgent
from common.server import utils
from common.server.task_manager import InMemoryTaskManager
from common.types import (
    Artifact,
    InternalError,
    InvalidParamsError,
    JSONRPCResponse,
    Message,
    PushNotificationConfig,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskSendParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from common.utils.push_notification_auth import PushNotificationSenderAuth

logger = logging.getLogger(__name__)


class AgentTaskManager(InMemoryTaskManager):
    """
    Manages the lifecycle of tasks for the LangGraph `ReactAgent`.

    This class extends `InMemoryTaskManager` to provide specialized handling
    for tasks executed by the `ReactAgent`. It is responsible for:
    - Receiving and validating task requests (both standard and streaming).
    - Invoking the `ReactAgent` with the user's query.
    - Processing synchronous and asynchronous (streaming) responses from the agent.
    - Updating task status and artifacts in the persistent store.
    - Managing Server-Sent Events (SSE) for real-time updates to clients.
    - Handling push notifications for task status changes.
    """
    def __init__(
        self,
        agent: ReactAgent,
        notification_sender_auth: PushNotificationSenderAuth,
    ):
        """
        Initializes the AgentTaskManager.

        Args:
            agent: An instance of `ReactAgent` that will execute the tasks.
            notification_sender_auth: An instance of `PushNotificationSenderAuth`
                                      used for authenticating and sending push
                                      notifications.
        """
        super().__init__()
        self.agent = agent
        self.notification_sender_auth = notification_sender_auth

    def _get_user_query(self, task_send_params: TaskSendParams) -> str:
        """
        Extracts the user's query text from the task parameters.

        Currently, this method assumes the first part of the message is a `TextPart`.

        Args:
            task_send_params: The parameters of the task request.

        Returns:
            The text of the user's query.

        Raises:
            ValueError: If the first part of the message is not a `TextPart` or
                        if no parts are present.
        """
        if not task_send_params.message.parts:
            raise ValueError('Message contains no parts.')
        part = task_send_params.message.parts[0]
        if not isinstance(part, TextPart):
            raise ValueError('Only text parts are supported')
        return part.text

    def _validate_request(
        self, request: SendTaskRequest | SendTaskStreamingRequest
    ) -> JSONRPCResponse | None:
        """
        Validates the incoming task request.

        Checks for:
        - Compatibility between the client's accepted output modes and the agent's
          supported content types.
        - Presence of a push notification URL if push notifications are requested.

        Args:
            request: The task request (either `SendTaskRequest` or
                     `SendTaskStreamingRequest`).

        Returns:
            A `JSONRPCResponse` with an error if validation fails, otherwise `None`.
        """
        task_send_params: TaskSendParams = request.params
        if not utils.are_modalities_compatible(
            task_send_params.acceptedOutputModes,
            self.agent.SUPPORTED_CONTENT_TYPES, # type: ignore
        ):
            logger.warning(
                'Unsupported output mode. Received %s, Support %s',
                task_send_params.acceptedOutputModes,
                self.agent.SUPPORTED_CONTENT_TYPES, # type: ignore
            )
            return utils.new_incompatible_types_error(request.id)

        if (
            task_send_params.pushNotification
            and not task_send_params.pushNotification.url
        ):
            logger.warning('Push notification URL is missing')
            return JSONRPCResponse(
                id=request.id,
                error=InvalidParamsError( # type: ignore
                    message='Push notification URL is missing'
                ),
            )

        return None

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """
        Handles a non-streaming 'send task' request.

        This method performs the following steps:
        1. Validates the request using `_validate_request`.
        2. If push notifications are configured, verifies and sets the push
           notification info.
        3. Creates or updates the task in the store, setting its initial state to `WORKING`.
        4. Sends an initial task status notification (if push notifications are enabled).
        5. Extracts the user query from the request.
        6. Invokes the `ReactAgent`'s synchronous `invoke` method.
        7. Processes the agent's response using `_process_agent_response` to finalize
           the task state and artifacts.
        8. Returns a `SendTaskResponse` with the final task result or an error.

        Args:
            request: The `SendTaskRequest` from the client.

        Returns:
            A `SendTaskResponse` containing the task result or an error.
        """
        validation_error = self._validate_request(request)
        if validation_error:
            return SendTaskResponse(id=request.id, error=validation_error.error) # type: ignore

        if request.params.pushNotification:
            if not await self.set_push_notification_info(
                request.params.id, request.params.pushNotification # type: ignore
            ):
                return SendTaskResponse(
                    id=request.id,
                    error=InvalidParamsError( # type: ignore
                        message='Push notification URL is invalid'
                    ),
                )

        await self.upsert_task(request.params) # type: ignore
        task = await self.update_store(
            request.params.id, TaskStatus(state=TaskState.WORKING), None # type: ignore
        )
        await self.send_task_notification(task)

        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)
        try:
            agent_response = self.agent.invoke(
                query, task_send_params.sessionId # type: ignore
            )
        except Exception as e:
            logger.error(f'Error invoking agent: {e}')
            # It's generally better to return an error response than raise ValueError here
            # For now, matching existing behavior.
            raise ValueError(f'Error invoking agent: {e}')
        return await self._process_agent_response(request, agent_response)

    async def on_send_task_subscribe(
        self, request: SendTaskStreamingRequest
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        """
        Handles a streaming 'send task' request (SSE subscription).

        This method sets up a Server-Sent Events (SSE) stream for the client:
        1. Validates the request using `_validate_request`.
        2. Creates or updates the task in the store.
        3. If push notifications are configured, verifies and sets the push
           notification info.
        4. Sets up an SSE event queue for the client to consume.
        5. Spawns a background asyncio task (`_run_streaming_agent`) to execute
           the agent's streaming logic and populate the SSE queue.
        6. Returns an `AsyncIterable` that the server can use to send SSE events
           to the client, or a `JSONRPCResponse` if an initial error occurs.

        Args:
            request: The `SendTaskStreamingRequest` from the client.

        Returns:
            An `AsyncIterable[SendTaskStreamingResponse]` for SSE events,
            or a `JSONRPCResponse` containing an error.
        """
        try:
            error = self._validate_request(request)
            if error:
                return error

            await self.upsert_task(request.params) # type: ignore

            if request.params.pushNotification:
                if not await self.set_push_notification_info(
                    request.params.id, request.params.pushNotification # type: ignore
                ):
                    return JSONRPCResponse(
                        id=request.id,
                        error=InvalidParamsError( # type: ignore
                            message='Push notification URL is invalid'
                        ),
                    )

            task_send_params: TaskSendParams = request.params
            sse_event_queue = await self.setup_sse_consumer(
                task_send_params.id, False
            )

            asyncio.create_task(self._run_streaming_agent(request))

            return self.dequeue_events_for_sse( # type: ignore
                request.id, task_send_params.id, sse_event_queue
            )
        except Exception as e:
            logger.error(f'Error in SSE stream: {e}')
            print(traceback.format_exc())
            return JSONRPCResponse(
                id=request.id,
                error=InternalError( # type: ignore
                    message='An error occurred while streaming the response'
                ),
            )

    async def _run_streaming_agent(self, request: SendTaskStreamingRequest):
        """
        Executes the `ReactAgent`'s streaming logic for an SSE task.

        This method is run as a background asyncio task. It:
        1. Extracts the user query.
        2. Calls the `ReactAgent.stream()` method to get an async iterable of
           agent responses.
        3. For each item received from the agent's stream:
           a. Determines the current task state (`WORKING`, `INPUT_REQUIRED`, `COMPLETED`).
           b. Formats messages and artifacts.
           c. Updates the task in the store using `update_store`.
           d. Sends push notifications if enabled.
           e. Enqueues `TaskArtifactUpdateEvent` and `TaskStatusUpdateEvent` into
              the SSE queue for the client.
        4. If an exception occurs during streaming, it enqueues an `InternalError`
           into the SSE queue.

        Args:
            request: The `SendTaskStreamingRequest` that initiated the stream.
        """
        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)

        try:
            async for item in self.agent.stream(
                query, task_send_params.sessionId # type: ignore
            ):
                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']
                artifact = None
                message = None
                parts = [{'type': 'text', 'text': item['content']}] # type: ignore
                end_stream = False

                if not is_task_complete and not require_user_input:
                    task_state = TaskState.WORKING
                    message = Message(role='agent', parts=parts) # type: ignore
                elif require_user_input:
                    task_state = TaskState.INPUT_REQUIRED
                    message = Message(role='agent', parts=parts) # type: ignore
                    end_stream = True
                else:
                    task_state = TaskState.COMPLETED
                    artifact = Artifact(parts=parts, index=0, append=False) # type: ignore
                    end_stream = True

                task_status = TaskStatus(state=task_state, message=message) # type: ignore
                latest_task = await self.update_store(
                    task_send_params.id,
                    task_status,
                    None if artifact is None else [artifact],
                )
                await self.send_task_notification(latest_task)

                if artifact:
                    task_artifact_update_event = TaskArtifactUpdateEvent( # type: ignore
                        id=task_send_params.id, artifact=artifact
                    )
                    await self.enqueue_events_for_sse( # type: ignore
                        task_send_params.id, task_artifact_update_event
                    )

                task_update_event = TaskStatusUpdateEvent( # type: ignore
                    id=task_send_params.id, status=task_status, final=end_stream
                )
                await self.enqueue_events_for_sse( # type: ignore
                    task_send_params.id, task_update_event
                )

        except Exception as e:
            logger.error(f'An error occurred while streaming the response: {e}')
            await self.enqueue_events_for_sse( # type: ignore
                task_send_params.id,
                InternalError( # type: ignore
                    message=f'An error occurred while streaming the response: {e}'
                ),
            )

    async def _process_agent_response(
        self, request: SendTaskRequest, agent_response: dict
    ) -> SendTaskResponse:
        """
        Processes the synchronous response from the `ReactAgent.invoke` method.

        This method is called after the agent has finished its execution for a
        non-streaming task. It:
        1. Determines the final task state (`INPUT_REQUIRED` or `COMPLETED`) based
           on the `agent_response`.
        2. Creates an `Artifact` if the task is completed with content.
        3. Updates the task in the store with the final status and artifact(s).
        4. Appends the final state to the task's history.
        5. Sends a final push notification if enabled.
        6. Returns a `SendTaskResponse` with the complete task details.

        Args:
            request: The original `SendTaskRequest`.
            agent_response: The dictionary returned by `ReactAgent.invoke`.
                            Expected keys: 'content', 'require_user_input'.

        Returns:
            A `SendTaskResponse` containing the finalized task.
        """
        task_send_params: TaskSendParams = request.params
        task_id = task_send_params.id
        history_length = task_send_params.historyLength
        task_status = None

        parts = [{'type': 'text', 'text': agent_response['content']}] # type: ignore
        artifact = None
        if agent_response['require_user_input']:
            task_status = TaskStatus( # type: ignore
                state=TaskState.INPUT_REQUIRED,
                message=Message(role='agent', parts=parts), # type: ignore
            )
        else:
            task_status = TaskStatus(state=TaskState.COMPLETED) # type: ignore
            artifact = Artifact(parts=parts) # type: ignore
        task = await self.update_store(
            task_id, task_status, None if artifact is None else [artifact]
        )
        task_result = self.append_task_history(task, history_length) # type: ignore
        await self.send_task_notification(task)
        return SendTaskResponse(id=request.id, result=task_result) # type: ignore

    async def send_task_notification(self, task: Task):
        """
        Sends a push notification for a task update if configured.

        It checks if push notification information is available for the given task ID.
        If so, it sends the complete task object (serialized) to the registered
        push notification URL using `PushNotificationSenderAuth`.

        Args:
            task: The `Task` object containing the latest update.
        """
        if not await self.has_push_notification_info(task.id):
            logger.info(f'No push notification info found for task {task.id}')
            return
        push_info = await self.get_push_notification_info(task.id)

        logger.info(f'Notifying for task {task.id} => {task.status.state}') # type: ignore
        await self.notification_sender_auth.send_push_notification(
            push_info.url, data=task.model_dump(exclude_none=True) # type: ignore
        )

    async def on_resubscribe_to_task(
        self, request # TODO: Add type hint for request if available from common.server
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        """
        Handles a client's request to resubscribe to an existing task's SSE stream.

        This is useful if a client disconnects and wants to resume receiving updates
        for an ongoing or completed task.

        Args:
            request: The resubscription request, typically containing the task ID.
                     (Specific type depends on the JSONRPC framework).

        Returns:
            An `AsyncIterable[SendTaskStreamingResponse]` for SSE events if successful,
            or a `JSONRPCResponse` with an error if the task cannot be resubscribed to
            (e.g., task not found, or other issues).
        """
        task_id_params: TaskIdParams = request.params
        try:
            sse_event_queue = await self.setup_sse_consumer(
                task_id_params.id, True # True indicates resubscription
            )
            return self.dequeue_events_for_sse( # type: ignore
                request.id, task_id_params.id, sse_event_queue
            )
        except Exception as e:
            logger.error(f'Error while reconnecting to SSE stream: {e}')
            return JSONRPCResponse(
                id=request.id,
                error=InternalError( # type: ignore
                    message=f'An error occurred while reconnecting to stream: {e}'
                ),
            )

    async def set_push_notification_info(
        self, task_id: str, push_notification_config: PushNotificationConfig
    ):
        """
        Sets the push notification configuration for a task, after verifying the URL.

        This method overrides the parent class's method to add a verification step.
        It uses `PushNotificationSenderAuth.verify_push_notification_url` to send
        a challenge request to the provided push notification URL to confirm its validity
        before storing the configuration.

        Args:
            task_id: The ID of the task.
            push_notification_config: The `PushNotificationConfig` containing the URL
                                      and other details.

        Returns:
            `True` if the URL was verified and the info was set, `False` otherwise.
        """
        # Verify the ownership of notification URL by issuing a challenge request.
        is_verified = (
            await self.notification_sender_auth.verify_push_notification_url(
                push_notification_config.url # type: ignore
            )
        )
        if not is_verified:
            return False

        await super().set_push_notification_info( # type: ignore
            task_id, push_notification_config
        )
        return True