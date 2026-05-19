# WestWood AI Server v4 - Roleplay tuning

Railway + FastAPI AI backend a WestWood chat AI karaktereihez.

## Kötelező Railway változók

- `OPENAI_API_KEY`
- `OPENAI_MODEL` ajánlott: `gpt-4o-mini`
- `CORS_ORIGINS` ajánlott: `https://westwood.hu,https://www.westwood.hu`

## Opcionális változók

- `MAX_HISTORY_MESSAGES` alapértelmezett: `24`
- `MAX_OUTPUT_TOKENS` alapértelmezett: `650`
- `DEFAULT_TEMPERATURE` alapértelmezett: `0.78`

## Teszt

- `/health`
- `/debug-openai`
- `POST /generate`
