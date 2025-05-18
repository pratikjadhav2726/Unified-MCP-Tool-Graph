# test_client.py
import asyncio
from a2a import A2AClient, Message, TextContent, MessageRole

async def main():
    client = A2AClient("http://localhost:10000")
    message = Message(
        content=TextContent(text="Plan a trip to Paris."),
        role=MessageRole.USER
    )
    response = await client.send_message(message)
    print(response.content.text)

if __name__ == "__main__":
    asyncio.run(main())