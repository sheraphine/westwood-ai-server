import os
import logging
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("westwood-ai-server")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "450"))

# Comma-separated origins. Default keeps it useful for testing and for WordPress calls.
# Example on Railway: CORS_ORIGINS=https://westwood.hu,https://www.westwood.hu
cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app = FastAPI(
    title="WestWood AI Server",
    version="1.0.0",
    description="AI reply service for the WestWood Fantasy Roleplay WordPress chat plugin.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str = Field(default="", max_length=6000)


class GenerateRequest(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=180)
    messages: List[ChatMessage] = Field(default_factory=list)
    # Optional future-proof fields. The current WordPress plugin does not need them,
    # but keeping them here prevents errors if we later send richer character data.
    character_description: Optional[str] = Field(default=None, max_length=4000)
    room_name: Optional[str] = Field(default=None, max_length=180)


class GenerateResponse(BaseModel):
    reply: str


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "WestWood AI Server",
        "endpoints": ["GET /health", "POST /generate"],
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "openai_key_configured": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
    }


def build_system_prompt(character_name: str, character_description: Optional[str] = None) -> str:
    base = f"""
Te a WestWood Fantasy Roleplay oldal egyik AI karaktere vagy.
A karaktered neve: {character_name}.

Feladatod:
- magyarul válaszolj,
- szerepjátékos chatüzenetet írj,
- maradj a karakter szerepében,
- ne magyarázd, hogy mesterséges intelligencia vagy,
- ne írj teljes jelenetet mindenki helyett,
- ne irányítsd durván más játékos karakterét,
- legfeljebb 1-3 közepes bekezdésben válaszolj,
- természetes, karakteres, de nem túl hosszú választ adj.

Formátum:
- csak a karakter válaszát add vissza,
- ne írd elé a karakter nevét,
- ne használj JSON-t vagy markdown címsorokat.
""".strip()

    if character_description:
        base += "\n\nKarakterleírás / személyiség:\n" + character_description.strip()

    return base


@app.post("/generate", response_model=GenerateResponse)
def generate_reply(payload: GenerateRequest):
    if client is None:
        logger.error("OPENAI_API_KEY is missing")
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nincs beállítva a szerveren.")

    clean_history = []
    for msg in payload.messages[-MAX_HISTORY_MESSAGES:]:
        content = (msg.content or "").strip()
        if not content:
            continue
        clean_history.append({"role": msg.role, "content": content})

    if not clean_history:
        clean_history.append({
            "role": "user",
            "content": "A chatben még kevés előzmény van. Reagálj röviden, karakteresen, magyarul.",
        })

    input_messages = [
        {"role": "system", "content": build_system_prompt(payload.character_name, payload.character_description)},
        *clean_history,
    ]

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=input_messages,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:
        logger.exception("OpenAI request failed")
        raise HTTPException(status_code=502, detail=f"OpenAI hívás sikertelen: {type(exc).__name__}") from exc

    reply = (getattr(response, "output_text", "") or "").strip()

    if not reply:
        logger.error("OpenAI response did not contain output_text: %s", response)
        raise HTTPException(status_code=502, detail="Az OpenAI válasza üres volt.")

    return GenerateResponse(reply=reply)
