import json
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
from tools import (
    ANALYST_SCHEMAS,
    ANALYST_TOOLS,
    COACH_SCHEMAS,
    COACH_TOOLS,
    ToolError,
)
from tools.coach import *  # noqa: F401,F403 — triggers tool registration
from tools.analyst import *  # noqa: F401,F403 — triggers tool registration

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
    api_messages = [
        {
            "role": "user" if m["role"] == "tool" else m["role"],
            "content": m["content"],
        }
        for m in history
    ]

    persona = conv["persona"]
    system = COACH_SYSTEM if persona == "coach" else ANALYST_SYSTEM
    model = llm.pick_model(body.message)
    tools_registry = COACH_TOOLS if persona == "coach" else ANALYST_TOOLS
    tools_schema = COACH_SCHEMAS if persona == "coach" else ANALYST_SCHEMAS

    MAX_HOPS = 4
    resp = None
    for hop in range(MAX_HOPS):
        resp = await llm.chat(
            messages=api_messages,
            system=system,
            model=model,
            tools=tools_schema,
            max_tokens=1024,
        )
        conversations.append_message(
            conv_id,
            "assistant",
            resp["content"],
            model=resp["usage"]["model"],
            tokens_in=resp["usage"]["tokens_in"],
            tokens_out=resp["usage"]["tokens_out"],
            latency_ms=resp["usage"]["latency_ms"],
        )
        api_messages.append({"role": "assistant", "content": resp["content"]})

        if resp["stop_reason"] != "tool_use":
            break

        tool_results = []
        for block in resp["content"]:
            if block.get("type") != "tool_use":
                continue
            try:
                fn = tools_registry[block["name"]]
                result = await fn(block["input"], user)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result),
                })
            except (KeyError, ToolError) as e:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": f"Error: {e}",
                    "is_error": True,
                })

        conversations.append_message(conv_id, "tool", tool_results)
        api_messages.append({"role": "user", "content": tool_results})

    return {"content": resp["content"], "usage": resp["usage"]}
