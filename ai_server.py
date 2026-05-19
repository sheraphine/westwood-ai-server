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
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "24"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "650"))
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.78"))

cors_raw = os.getenv("CORS_ORIGINS", "https://westwood.hu,https://www.westwood.hu")
CORS_ORIGINS = [x.strip() for x in cors_raw.split(",") if x.strip()]

app = FastAPI(title=APP_NAME, version="4.0.0")
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
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def normalize_messages(raw_messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in raw_messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        speaker = clean_text(item.get("character_name") or item.get("name") or item.get("sender") or "Ismeretlen")
        text = clean_text(item.get("message") or item.get("content"))
        if not text:
            continue
        # Ne engedjük, hogy egy üzenet túlzottan szétnyomja a promptot.
        if len(text) > 1800:
            text = text[:1800].rstrip() + "…"
        normalized.append({"speaker": speaker, "text": text})
    return normalized


def build_profile_block(payload: GenerateRequest) -> str:
    profile = payload.character_profile or {}
    name = clean_text(profile.get("name")) or clean_text(payload.character_name)
    style = clean_text(profile.get("style"))
    backstory = clean_text(profile.get("backstory"))
    memory = clean_text(profile.get("memory"))

    parts: List[str] = [f"Név: {name}"]
    if style:
        parts.append(f"Stílus / személyiség / beszédmód: {style}")
    if backstory:
        parts.append(f"Háttértörténet / aktuális helyzet: {backstory}")
    if memory:
        parts.append(f"Memória / fontos kapcsolatok és emlékek: {memory}")
    return "\n".join(parts)


def build_conversation_block(history: List[Dict[str, str]], character_name: str) -> str:
    if not history:
        return "Még nincs érdemi előzmény a szobában."

    lines: List[str] = []
    for msg in history:
        speaker = msg["speaker"]
        text = msg["text"]
        marker = " (te)" if speaker.strip().lower() == character_name.strip().lower() else ""
        lines.append(f"{speaker}{marker}: {text}")
    return "\n".join(lines)


def strip_name_prefix(reply: str, character_name: str) -> str:
    reply = clean_text(reply)
    if not reply:
        return reply

    # Tipikus modell-előtagok eltávolítása: "Michael Desmond:", "Michael Desmond -", stb.
    names_to_strip = [character_name.strip()]
    # Biztonsági variáció: ha sok szóközzel vagy dupla kettősponttal kezd.
    for name in names_to_strip:
        if not name:
            continue
        escaped = re.escape(name)
        for _ in range(3):
            reply = re.sub(rf"^\s*{escaped}\s*[:：\-–—]+\s*", "", reply, flags=re.IGNORECASE).strip()

    # Általános, nem kívánt előtagok.
    for _ in range(2):
        reply = re.sub(r"^\s*(AI|Asszisztens|Válasz|Üzenet|Narráció|Reakció)\s*[:：\-–—]+\s*", "", reply, flags=re.IGNORECASE).strip()

    # Ne csomagolja idézőjelbe a teljes választ.
    reply = reply.strip().strip('"').strip("'").strip()
    return reply


def normalize_reply(reply: str, character_name: str) -> str:
    reply = strip_name_prefix(reply, character_name)
    # Túl sok üres sor takarítása.
    reply = re.sub(r"\n{3,}", "\n\n", reply).strip()
    return reply


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
        "version": "4.0.0",
        "max_history_messages": MAX_HISTORY_MESSAGES,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
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
    conversation_block = build_conversation_block(history, character_name)

    latest = history[-1] if history else None
    latest_speaker = latest["speaker"] if latest else "nincs"
    latest_text = latest["text"] if latest else "nincs"

    system_prompt = f"""
Te {character_name} vagy a West-Wood Fantasy Roleplay chaten.

ALAPSZABÁLYOK:
- Magyarul írj.
- Egyetlen szerepjátékos chatüzenetet adj vissza {character_name} nevében.
- A chat felület külön kiírja a karakter nevét, ezért SOHA ne írd a válasz elejére, hogy "{character_name}:".
- Ne írj OOC magyarázatot, technikai szöveget, címet, összefoglalót vagy alternatívákat.
- Ne mondd, hogy AI vagy.
- Ne beszélj más karakterek helyett, és ne döntsd el más karakterek érzéseit, gondolatait vagy reakcióit.
- Ne oldd meg túl gyorsan a konfliktust; inkább adj karakterhű reakciót, ami továbbviheti a jelenetet.
- Elsősorban a legutolsó üzenetre reagálj, de vedd figyelembe az előzményeket is.
- Használhatsz *cselekvést* és párbeszédet, ahogy a chatben is szokás.
- A válasz legyen természetes, nem sablonos tanácsadás. Ha feszült a helyzet, konkrétan a helyzetre reagálj.
- Terjedelem: általában 2-6 mondat. Lehet rövidebb, ha a jelenet ezt kívánja.

A karakter adatlapja, amit kötelező figyelembe venni:
{profile_block}
""".strip()

    if payload.room_name:
        system_prompt += f"\n\nJelenlegi szoba: {payload.room_name}."

    if payload.instruction:
        # A WordPressből érkező instrukciót megtartjuk, de nem engedjük felülírni az alapszabályokat.
        system_prompt += "\n\nKiegészítő oldal-instrukciók:\n" + clean_text(payload.instruction)

    user_prompt = f"""
Beszélgetési előzmény időrendben:
{conversation_block}

Legutóbbi üzenet:
{latest_speaker}: {latest_text}

Most írj egyetlen következő szerepjátékos üzenetet {character_name} nevében.
Ne kezdd a választ névvel vagy előtaggal. Csak a chatüzenet törzse jöjjön.
""".strip()

    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
        )
        raw_reply = completion.choices[0].message.content or ""
        reply = normalize_reply(raw_reply, character_name)
        if not reply:
            raise HTTPException(status_code=502, detail="Az OpenAI üres választ adott.")
        return {
            "ok": True,
            "reply": reply,
            "character_name": character_name,
            "model": OPENAI_MODEL,
            "version": "4.0.0",
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"OpenAI generate error: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(status_code=502, detail=f"OpenAI generálási hiba: {type(exc).__name__}: {exc}")
