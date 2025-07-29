from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

app = FastAPI()

# CORS beállítások
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI API kulcs
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.post("/generate")
async def generate_reply(request: Request):
    try:
        data = await request.json()
        character_name = data.get("character_name")
        messages = data.get("messages")

        if not character_name or not messages:
            return {"error": "character_name és messages kötelező"}

        # System prompt
        system_prompt = f"Te egy szerepjátékos karakter vagy: {character_name}. Válaszolj fantasy stílusban a következő beszélgetésre."

        # Összeállított prompt lista
        chat_messages = [{"role": "system", "content": system_prompt}] + messages

        # OpenAI hívás
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=chat_messages,
            temperature=0.8,
        )

        reply = response["choices"][0]["message"]["content"]
        return {"reply": reply}

    except Exception as e:
        return {"error": str(e)}
