import os
import re
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

app = FastAPI(title=APP_NAME, version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class GenerateRequest(BaseModel):
    character_name: str = Field(default="AI karakter")
    room_name: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    instruction: Optional[str] = None
    character_profile: Optional[Dict[str, Any]] = None


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_messages(raw_messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in raw_messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        speaker = clean_text(item.get("character_name") or item.get("name") or item.get("sender") or "Ismeretlen")
        text = clean_text(item.get("message") or item.get("content"))
        if not text:
            continue
        normalized.append({"role": "user", "content": f"{speaker}: {text}"})
    return normalized


def strip_name_prefix(reply: str, character_name: str) -> str:
    reply = clean_text(reply)
    if not reply:
        return reply
    escaped = re.escape(character_name.strip())
    if escaped:
        reply = re.sub(rf"^\s*{escaped}\s*[:：\-–—]+\s*", "", reply, flags=re.IGNORECASE)
    # Általános biztonsági tisztítás, ha a modell idézőjelben vagy szereplőként kezdené.
    reply = re.sub(r"^\s*(AI|Asszisztens|Válasz)\s*[:：\-–—]+\s*", "", reply, flags=re.IGNORECASE)
    return reply.strip()


def build_profile_block(payload: GenerateRequest) -> str:
    profile = payload.character_profile or {}
    style = clean_text(profile.get("style"))
    backstory = clean_text(profile.get("backstory"))
    memory = clean_text(profile.get("memory"))
    parts: List[str] = []
    if style:
        parts.append(f"Stílus/jellem: {style}")
    if backstory:
        parts.append(f"Háttértörténet/leírás: {backstory}")
    if memory:
        parts.append(f"Memória/fontos emlékek: {memory}")
    return "\n".join(parts)


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
        "version": "3.0.0",
    }


@app.get("/debug-openai")
def debug_openai() -> Dict[str, Any]:
    if client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nincs beállítva.")
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "Válaszolj egyetlen szóval: OK"}],
            max_tokens=10,
        )
        return {"ok": True, "model": OPENAI_MODEL, "reply": completion.choices[0].message.content}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI kapcsolat hiba: {type(exc).__name__}: {exc}")


@app.post("/generate")
async def generate(payload: GenerateRequest, request: Request) -> Dict[str, Any]:
    if client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nincs beállítva a Railway Variables alatt.")

    character_name = clean_text(payload.character_name) or "AI karakter"
    history = normalize_messages(payload.messages)
    profile_block = build_profile_block(payload)

    system_prompt = (
        f"Te {character_name} vagy a West-Wood Fantasy Roleplay chaten.\n"
        "Magyarul válaszolj, szerepjátékos stílusban, természetesen és karakterben maradva.\n"
        "Soha ne írd a válasz elejére a karakter nevét.\n"
        f"Tilos ilyen előtagot használnod: '{character_name}:'\n"
        "Csak a karakter tényleges üzenetét add vissza, névelőtag, magyarázat, rendszerüzenet és idézőjel nélkül.\n"
        "Ne mondd, hogy AI vagy. Ne adj technikai magyarázatot.\n"
        "Ha kevés a kontextus, röviden, de karakterben reagálj."
    )

    if payload.room_name:
        system_prompt += f"\nA jelenlegi szoba neve: {payload.room_name}."
    if profile_block:
        system_prompt += "\n\nA karakter adatlapja, amit kötelező figyelembe venni:\n" + profile_block
    if payload.instruction:
        system_prompt += "\n\nKiegészítő instrukció a WordPress oldalról:\n" + payload.instruction

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": (
            f"Írj egy rövid, természetes szerepjátékos választ {character_name} nevében a fenti beszélgetésre. "
            f"A válasz NE kezdődjön így: '{character_name}:'. Csak maga az üzenet jöjjön."
        ),
    })

    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.85,
        )
        reply = strip_name_prefix(completion.choices[0].message.content or "", character_name)
        if not reply:
            raise HTTPException(status_code=502, detail="Az OpenAI üres választ adott.")
        return {"ok": True, "reply": reply, "character_name": character_name, "model": OPENAI_MODEL}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"OpenAI generate error: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(status_code=502, detail=f"OpenAI generálási hiba: {type(exc).__name__}: {exc}")
