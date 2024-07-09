from typing import AsyncGenerator, NoReturn
import os
import uvicorn
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, AsyncAssistantEventHandler, override

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(api_key="sk-proj-dDZNhXMqgrkXj1SVBwmIT3BlbkFJivViBzo2S6LoHwEztZt1")

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://10aa-41-224-249-253.ngrok-free.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("../ai-assistant/index.html") as f:
    html = f.read()

class CustomEventHandler(AsyncAssistantEventHandler):
    def __init__(self, websocket: WebSocket):
        super().__init__()
        self.websocket = websocket

    @override
    async def on_text_created(self, text):
        await self.websocket.send_text(text.value)

    @override
    async def on_text_delta(self, delta, snapshot):
        if delta.annotations == None :
            await self.websocket.send_text(delta.value)


async def get_ai_response(websocket: WebSocket, content: str, thread_id: str) -> AsyncGenerator[str, None]:
    """
    OpenAI Assistant Response
    """
    assistant_id = "asst_0s7fWfqI05Bd3DwiAEP7KgLx"

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
        event_handler=event_handler,
    ) as stream:
        async for event in stream:
            if 'choices' in event and len(event['choices']) > 0:
                text = event['choices'][0]['message']['content']
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

    # Create a new thread for this interaction
    thread = await client.beta.threads.create()
    thread_id = thread.id

    while True:
        message = await websocket.receive_text()
        async for text in get_ai_response(websocket, message, thread_id):
            await websocket.send_text(text)


@app.get("/tts")
async def get_voice_response(content: str):
    """
    OpenAI Assistant Text To Speech
    """
    speech_file_path = "../ai-assistant/speech.mp3"
    response = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=content
    )
    response.stream_to_file(speech_file_path)
    return FileResponse(speech_file_path)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        log_level="debug",
        reload=True,
    )
