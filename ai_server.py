from fastapi import FastAPI, Request
import openai
import requests
import os

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
WORDPRESS_API_URL = os.getenv("WORDPRESS_API_URL")

@app.post("/generate")
async def generate_reply(request: Request):
    data = await request.json()
    character_id = data.get("character_id")
    room_id = data.get("room_id")

    if not character_id or not room_id:
        return {"error": "character_id és room_id kötelező"}

    prompt = f"Te egy szerepjátékos karakter vagy. Karakter ID: {character_id}, Szoba ID: {room_id}. Válaszolj fantasy stílusban."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Te egy fantasy szerepjáték karakter vagy."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )

        reply = response['choices'][0]['message']['content']

        wp_response = requests.post(WORDPRESS_API_URL, json={
            "character_id": character_id,
            "room_id": room_id,
            "message": reply
        })

        return {
            "status": "ok",
            "reply": reply,
            "wp_response_code": wp_response.status_code,
            "wp_response_text": wp_response.text
        }

    except Exception as e:
        return {"error": str(e)}
