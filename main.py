from typing import AsyncGenerator, NoReturn
import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI, AsyncAssistantEventHandler, override

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("../ai-assistant/index.html") as f:
    html = f.read()

class CustomEventHandler(AsyncAssistantEventHandler):
    def __init__(self, websocket: WebSocket):
        super().__init__()
        self.websocket = websocket

    @override
    async def on_text_delta(self, delta, snapshot):
        if delta.annotations == None :
            await self.websocket.send_text(delta.value)

async def get_ai_response(websocket: WebSocket, content: str) -> AsyncGenerator[str, None]:
    """
    OpenAI Assistant Response
    """
    assistant_id = "asst_oVtc8KTgDfLiqnYVQn5AUQLB"

    # Create a new thread for this interaction
    thread = await client.beta.threads.create()
    thread_id = thread.id

    # Send the user message to the assistant thread
    await client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content
    )

    # Use a custom event handler to handle assistant responses
    event_handler = CustomEventHandler(websocket=websocket)

    # Stream responses from the assistant
    async with client.beta.threads.runs.stream(
        assistant_id=assistant_id,
        thread_id=thread_id,
        instructions="Please address the user as Jane Doe. The user has a premium account.",
        event_handler=event_handler,
    ) as stream:
        async for event in stream:
            if 'choices' in event and len(event['choices']) > 0:
                text = event['choices'][0]['message']['content']
                print(f"EVEEEENT::::{event}")
                yield text

@app.get("/")
async def web_app() -> HTMLResponse:
    """
    Web App
    """
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> NoReturn:
    """
    Websocket for AI responses
    """
    await websocket.accept()
    while True:
        message = await websocket.receive_text()
        async for text in get_ai_response(websocket, message):
            await websocket.send_text(text)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        log_level="debug",
        reload=True,
    )
