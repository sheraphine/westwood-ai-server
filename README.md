# WestWood AI Server

Railway/FastAPI AI szerver a WestWood chat AI karakter válaszaihoz.

## Endpointok

- `GET /health` – ellenőrzés
- `GET /debug-openai` – OpenAI kapcsolat teszt
- `POST /generate` – AI válasz generálás

## Railway Variables

- `OPENAI_API_KEY`
- `OPENAI_MODEL` = `gpt-4o-mini`
- `CORS_ORIGINS` = `https://westwood.hu,https://www.westwood.hu`
- `MAX_HISTORY_MESSAGES` = `20`
- `MAX_OUTPUT_TOKENS` = `450`
