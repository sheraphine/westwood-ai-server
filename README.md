# WestWood AI Server

Ez egy Railway-re telepíthető FastAPI szerver a WestWood WordPress chat AI válasz funkciójához.

## Fájlok

- `ai_server.py` – FastAPI alkalmazás, benne a `POST /generate` végponttal.
- `requirements.txt` – Python csomagok.
- `Procfile` – indítási parancs Railway számára.
- `railway.json` – Railway/Nixpacks deploy beállítás.

## A WordPress plugin ezt hívja

```text
POST https://westwood-ai-server.up.railway.app/generate
```

A kérés formája:

```json
{
  "character_name": "Michael Desmond",
  "messages": [
    {"role": "user", "content": "Choson Woojoon: Próba"}
  ]
}
```

A válasz formája:

```json
{
  "reply": "Az AI karakter válasza..."
}
```

## Railway környezeti változók

Kötelező:

```text
OPENAI_API_KEY=sk-...
```

Ajánlott:

```text
OPENAI_MODEL=gpt-4o-mini
CORS_ORIGINS=https://westwood.hu,https://www.westwood.hu
MAX_HISTORY_MESSAGES=20
MAX_OUTPUT_TOKENS=450
```

## Ellenőrzés telepítés után

Böngészőben:

```text
https://westwood-ai-server.up.railway.app/health
```

Ha működik, ilyesmit ad:

```json
{
  "ok": true,
  "openai_key_configured": true,
  "model": "gpt-4o-mini"
}
```

A `POST /generate` végpontot a WordPress plugin fogja hívni.
