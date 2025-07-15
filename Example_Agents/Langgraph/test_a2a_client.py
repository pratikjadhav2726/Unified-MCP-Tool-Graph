import json
import uuid
import asyncio
from typing import Any
import httpx
import requests
from a2a.client import A2AClient
from a2a.types import AgentCard, SendMessageRequest, MessageSendParams, Message, Part, TextPart, Role

def filter_agent_card_fields(data):
    allowed = set(AgentCard.__annotations__.keys())
    return {k: v for k, v in data.items() if k in allowed}

class A2AToolClient:
    """A2A client for testing."""
    def __init__(self, default_timeout: float = 120.0):
        self._agent_info_cache: dict[str, dict[str, Any] | None] = {}
        self.default_timeout = default_timeout

    def add_remote_agent(self, agent_url: str):
        normalized_url = agent_url.rstrip('/')
        if normalized_url not in self._agent_info_cache:
            self._agent_info_cache[normalized_url] = None

    def list_remote_agents(self) -> list[dict[str, Any]]:
        if not self._agent_info_cache:
            return []
        agent_infos = []
        for url, cached_info in self._agent_info_cache.items():
            if cached_info is not None:
                agent_infos.append(cached_info)
            else:
                try:
                    response = requests.get(f"{url}/.well-known/agent.json", timeout=5)
                    response.raise_for_status()
                    agent_data = response.json()
                    self._agent_info_cache[url] = agent_data
                    agent_infos.append(agent_data)
                except requests.RequestException as e:
                    print(f"Failed to fetch agent info from {url}: {e}")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse agent info from {url}: {e}")
        return agent_infos

    async def create_task(self, agent_url: str, message: str) -> str:
        timeout_config = httpx.Timeout(
            timeout=self.default_timeout,
            connect=10.0,
            read=self.default_timeout,
            write=10.0,
            pool=5.0
        )
        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            normalized_url = agent_url.rstrip('/')
            if normalized_url in self._agent_info_cache and self._agent_info_cache[normalized_url] is not None:
                agent_card_data = self._agent_info_cache[normalized_url]
            else:
                try:
                    agent_card_response = await httpx_client.get(f"{normalized_url}/.well-known/agent.json")
                    agent_card_response.raise_for_status()
                    agent_card_data = agent_card_response.json()
                    self._agent_info_cache[normalized_url] = agent_card_data
                except httpx.RequestError as e:
                    return f"Error fetching agent card from {normalized_url}: {e}"
                except json.JSONDecodeError as e:
                    return f"Error parsing agent card JSON from {normalized_url}: {e}"
            try:
                agent_card = AgentCard(**filter_agent_card_fields(agent_card_data))
            except Exception as e:
                return f"Error creating AgentCard from fetched data for {normalized_url}: {e}. Data: {agent_card_data}"
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card
            )
            part = Part(root=TextPart(text=message))
            # Print available Role values for debugging
            # print('Available Role values:', list(Role))
            user_role = None
            for r in Role:
                if str(r).lower().endswith('user') or str(r).lower() == 'user':
                    user_role = r
                    break
            if user_role is None:
                raise ValueError('No user role found in Role enum')
            message_obj = Message(
                role=user_role,
                parts=[part],
                messageId=uuid.uuid4().hex
            )
            send_params = MessageSendParams(message=message_obj)
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=send_params
            )
            try:
                response = await client.send_message(request)
            except httpx.RequestError as e:
                return f"Error sending message to {normalized_url}: {e}"
            try:
                response_dict = response.model_dump(mode='json', exclude_none=True)
                if 'result' in response_dict and 'artifacts' in response_dict['result']:
                    artifacts = response_dict['result']['artifacts']
                    for artifact in artifacts:
                        if 'parts' in artifact:
                            for part_item in artifact['parts']:
                                if 'text' in part_item:
                                    return part_item['text']
                return json.dumps(response_dict, indent=2)
            except Exception as e:
                print(f"Error parsing response: {e}")
                return str(response)

    def remove_remote_agent(self, agent_url: str):
        normalized_url = agent_url.rstrip('/')
        if normalized_url in self._agent_info_cache:
            del self._agent_info_cache[normalized_url]

if __name__ == "__main__":
    async def test():
        agent_url = "http://localhost:10020"
        client = A2AToolClient()
        client.add_remote_agent(agent_url)
        agents = client.list_remote_agents()
        print("Discovered agents:", agents)
        if not agents:
            print("No agents found at the given URL.")
            return
        # Send a test message
        result = await client.create_task(agent_url, "I want to post on linkedin using google search")
        print("A2A result:", result)
    asyncio.run(test()) 