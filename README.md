# WestWood AI Server v5

FastAPI + OpenAI szerver a WestWood szerepjátékos AI karakterekhez.

## Végpontok

- `GET /health`
- `GET /debug-openai`
- `POST /generate`

## Fontos változók Railway-ben

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
CORS_ORIGINS=https://westwood.hu,https://www.westwood.hu
MAX_HISTORY_MESSAGES=24
MAX_OUTPUT_TOKENS=650
ENABLE_MEMORY_UPDATE=1
MAX_MEMORY_UPDATE_TOKENS=120
```

## v5 újdonság

A `/generate` válasza már opcionálisan visszaadja:

```json
{
  "reply": "...",
  "memory_update": "..."
}
```

A `memory_update` rövid, tartós memória-bejegyzés. A WordPress plugin menti vissza az `ai_characters.memory` mezőbe.
