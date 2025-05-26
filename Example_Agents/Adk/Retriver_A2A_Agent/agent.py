"""
Example ADK (Agent Development Kit) agent that utilizes an MCP (Model Context Protocol)
toolset for dynamic tool retrieval.

This agent is designed to:
1. Connect to an MCP server (specifically, the Dynamic_tool_retriever_MCP).
2. Use the tools exposed by the MCP server to find relevant tools based on a task description.
3. Formulate a plan or response based on the retrieved tools.

The agent uses asynchronous operations to interact with the MCP server and process events.
"""
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part
# from Retriver_A2A_Agent.MCP_config_agent.agent import root_agent
from Utils.get_MCP_config import extract_config_from_github # This import is currently commented out

# Initialize the LiteLlm model to be used by the agent.
# Model: bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0
model = LiteLlm(model="bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0")

async def get_tools_async():
    """
    Asynchronously connects to the MCP server and retrieves the toolset.

    The MCP server is expected to be running the 'Dynamic_tool_retriever_MCP/server.py' script.
    It uses StdioServerParameters for communication, meaning it starts the server
    as a subprocess and communicates over stdin/stdout.

    Returns:
        A tuple containing:
        - tools (MCPToolset): The set of tools retrieved from the MCP server.
        - exit_stack (AsyncExitStack): An exit stack for managing the lifecycle
                                       of the MCP server connection.
    """
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command='python',
            args=["Dynamic_tool_retriever_MCP/server.py"]
        )
    )
    return tools, exit_stack

async def create_agent():
    """
    Asynchronously creates the ADK agent.

    This involves:
    1. Retrieving tools from the MCP server using `get_tools_async`.
    2. Defining the agent's properties like name, model, description, instruction, and tools.
       (Currently, a commented-out line suggests `extract_config_from_github` could also be added as a tool.)
       (Currently, a commented-out line suggests `root_agent` could be a sub-agent.)


    Returns:
        A tuple containing:
        - agent (Agent): The initialized ADK agent.
        - exit_stack (AsyncExitStack): The exit stack from `get_tools_async`,
                                       needed to close the MCP server connection later.
    """
    tools, exit_stack = await get_tools_async()
    # tools.append(extract_config_from_github)
    agent = Agent(
        name="retriver_Agent", # Corrected spelling from "retriver_Agent" to "retriever_Agent"
        model=model,
        description="Retrieves best tools for a given task description", # Corrected spelling
        instruction="find top 5 tools for the given task description. Summarize the flow of tools to solve the task",
        tools=tools,
        # sub_agents=[root_agent]
    )
    return agent, exit_stack

async def async_main():
    """
    Asynchronous main function to set up and run the ADK agent.

    Steps:
    1. Initializes in-memory session and artifact services.
    2. Creates a user session.
    3. Defines a sample user query.
    4. Creates the agent instance using `create_agent()`.
    5. Initializes the ADK Runner.
    6. Runs the agent with the user query using `runner.run_async()`.
    7. Processes the asynchronous event stream from the agent, printing each event
       and the final response.
    8. Ensures the MCP server connection is closed using the `exit_stack`.
    """
    # Initialize services
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    # Create a session
    session = session_service.create_session(
        state={},
        app_name='retriever_Agent', # Corrected spelling
        user_id='user_1',
        session_id='session_1',
    )

    # Define the user query
    query = "I want to post a linkedIn post about the latest trends in AI. "
    content = Content(role='user', parts=[Part(text=query)])

    # Create the agent and get the exit stack
    agent, exit_stack = await create_agent()

    # Initialize the runner
    runner = Runner(
        app_name='retriever_Agent', # Corrected spelling
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    # Run the agent and process the response
    events_async = runner.run_async(
        session_id=session.id,
        user_id=session.user_id,
        new_message=content
    )

    async for event in events_async:
        print(f"Event: {event}")
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            print(f"############# Final Response #############\n\n{final_response_text}")
            break

    # Close the MCP server connections
    await exit_stack.aclose()

# Entry point to run the asynchronous main function
if __name__ == "__main__":
    asyncio.run(async_main())