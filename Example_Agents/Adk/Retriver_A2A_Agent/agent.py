import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part
# from Retriver_A2A_Agent.MCP_config_agent.agent import root_agent
from Utils.get_MCP_config import extract_config_from_github

# Initialize the model
model = LiteLlm(model="bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0")

# Asynchronous function to get tools from the MCP server
async def get_tools_async():
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command='python',
            args=["Dynamic_tool_retriever_MCP/server.py"]
        )
    )
    return tools, exit_stack

# Asynchronous function to create the agent
async def create_agent():
    tools, exit_stack = await get_tools_async()
    # tools.append(extract_config_from_github)
    agent = Agent(
        name="retriver_Agent",
        model=model,
        description="Retrives best tools for a given task description",
        instruction="find top 5 tools for the given task description. Summarize the flow of tools to solve the task",
        tools=tools,
        # sub_agents=[root_agent]
    )
    return agent, exit_stack

# Asynchronous main function to run the agent
async def async_main():
    # Initialize services
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    # Create a session
    session = session_service.create_session(
        state={},
        app_name='retriver_Agent',
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
        app_name='retriver_Agent',
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

    # Close the MCP server connectionsss
    await exit_stack.aclose()

# Entry point to run the asynchronous main function
if __name__ == "__main__":
    asyncio.run(async_main())