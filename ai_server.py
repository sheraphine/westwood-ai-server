import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI

APP_NAME = "WestWood AI Server"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "450"))

cors_raw = os.getenv("CORS_ORIGINS", "https://westwood.hu,https://www.westwood.hu")
CORS_ORIGINS = [x.strip() for x in cors_raw.split(",") if x.strip()]

app = FastAPI(title=APP_NAME, version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class ChatMessage(BaseModel):
    character_name: Optional[str] = None
    name: Optional[str] = None
    message: Optional[str] = None
    content: Optional[str] = None
    role: Optional[str] = None


class GenerateRequest(BaseModel):
    character_name: str = Field(default="AI karakter")
    room_name: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    instruction: Optional[str] = None


def normalize_messages(raw_messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in raw_messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        speaker = str(item.get("character_name") or item.get("name") or item.get("sender") or "Ismeretlen").strip()
        text = str(item.get("message") or item.get("content") or "").strip()
        if not text:
            continue
        # A szerepjátékos előzményt user üzenetként adjuk át, benne a beszélő nevével.
        normalized.append({"role": "user", "content": f"{speaker}: {text}"})
    return normalized


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": APP_NAME,
        "routes": ["GET /health", "POST /generate", "GET /debug-openai"],
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "openai_key_configured": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "version": "2.0.0",
    }


@app.get("/debug-openai")
def debug_openai() -> Dict[str, Any]:
    """Gyors OpenAI-kapcsolat teszt. Nem ad vissza API-kulcsot."""
    if client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nincs beállítva.")
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "Válaszolj egyetlen szóval: OK"}],
            max_tokens=10,
        )
        return {
            "ok": True,
            "model": OPENAI_MODEL,
            "reply": completion.choices[0].message.content,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI kapcsolat hiba: {type(exc).__name__}: {exc}")


@app.post("/generate")
async def generate(payload: GenerateRequest, request: Request) -> Dict[str, Any]:
    if client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nincs beállítva a Railway Variables alatt.")

    character_name = (payload.character_name or "AI karakter").strip()
    history = normalize_messages(payload.messages)

    system_prompt = (
        f"Te {character_name} vagy a West-Wood Fantasy Roleplay chaten. "
        "Magyarul válaszolj, szerepjátékos stílusban, természetesen és karakterben maradva. "
        "Ne írj rendszerüzenetet, ne magyarázd, hogy AI vagy. "
        "Csak a karakter válaszát add vissza. "
        "Ha kevés a kontextus, reagálj röviden, de hangulatban illeszkedve."
    )

    if payload.room_name:
        system_prompt += f" A jelenlegi szoba neve: {payload.room_name}."
    if payload.instruction:
        system_prompt += f" Kiegészítő instrukció: {payload.instruction}"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": f"Írj egy rövid, természetes választ {character_name} nevében a fenti beszélgetésre."})

    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.85,
        )
        reply = (completion.choices[0].message.content or "").strip()
        if not reply:
            raise HTTPException(status_code=502, detail="Az OpenAI üres választ adott.")
        return {
            "ok": True,
            "reply": reply,
            "character_name": character_name,
            "model": OPENAI_MODEL,
        }
    except HTTPException:
        raise
    except Exception as exc:
        # A Railway logban is megjelenik, de a WordPress felé is adunk értelmes hibát.
        print(f"OpenAI generate error: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(status_code=502, detail=f"OpenAI generálási hiba: {type(exc).__name__}: {exc}")
