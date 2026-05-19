# WestWood AI Server v3

FastAPI + OpenAI szerver a WestWood AI karakter válaszokhoz.

Újdonság:
- figyelembe veszi a `character_profile` mezőt: style, backstory, memory
- erősen tiltja a `Karakter neve:` előtagot
- szerveroldalon is levágja a válasz elejéről a karakternevet, ha a modell mégis odateszi

Railway változók:
- OPENAI_API_KEY
- OPENAI_MODEL=gpt-4o-mini
- CORS_ORIGINS=https://westwood.hu,https://www.westwood.hu
- MAX_HISTORY_MESSAGES=20
- MAX_OUTPUT_TOKENS=450
