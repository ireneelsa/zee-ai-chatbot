from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import conversations
load_dotenv()
import llm
from auth import get_current_user
from personas import ANALYST_SYSTEM, COACH_SYSTEM

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    conversations.init_db()
    yield


app = FastAPI(title="Zee Standalone", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/conversations")
async def create_conversation(user=Depends(get_current_user)):
    account_type = user.get("account_type")
    if account_type not in ("creator", "company"):
        raise HTTPException(status_code=403, detail="Account type not allowed")
    persona = "coach" if account_type == "creator" else "analyst"
    conv = conversations.create_conversation(user["account_id"], persona)
    return {"conversation": conv}


@app.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, user=Depends(get_current_user)):
    conv = conversations.get_conversation(conv_id, user["account_id"])
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = conversations.list_messages(conv_id)
    return {"messages": messages}


class SendMessageBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@app.post("/conversations/{conv_id}/messages")
async def send_message(
    conv_id: str,
    body: SendMessageBody,
    user=Depends(get_current_user),
):
    conv = conversations.get_conversation(conv_id, user["account_id"])
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_content = [{"type": "text", "text": body.message}]
    conversations.append_message(conv_id, "user", user_content)

    history = conversations.list_messages(conv_id)
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]

    system = COACH_SYSTEM if conv["persona"] == "coach" else ANALYST_SYSTEM
    model = llm.pick_model(body.message)

    result = await llm.chat(
        messages=api_messages,
        system=system,
        model=model,
        tools=[],
        max_tokens=1024,
    )

    usage = result["usage"]
    conversations.append_message(
        conv_id,
        "assistant",
        result["content"],
        model=usage["model"],
        tokens_in=usage["tokens_in"],
        tokens_out=usage["tokens_out"],
        latency_ms=usage["latency_ms"],
    )

    return {"content": result["content"], "usage": usage}
