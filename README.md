# Caller ID Platform (live lookup, zonder eigen dataset)

Dit project levert een werkende basis die telefoonnummers ontvangt, normaliseert en via meerdere publieke bronnen verrijkt:
- lokale telecom-metadata (`phonenumbers`)
- NumVerify API (optioneel met API-key)
- SerpAPI (optioneel, API-key)
- DuckDuckGo web-scraping (publiek, met disclaimer)

Er wordt **geen eigen bronbestand geüpload**. Alles is live verrijking + caching.

## Snelle start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Of met Docker:

```bash
docker compose up --build
```

Open `http://localhost:8000` voor de UI.

## API

- `GET /health`
- `GET /api/v1/sources`
- `POST /api/v1/lookup`
  - body: `{ "phone_number": "06 12 34 56 78" }`
- `POST /api/v1/lookup/bulk`
  - body: `{ "numbers": ["06...","06..."], "async_mode": true|false, "max_items": 100 }`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/requests/{request_id}`
- `GET /api/v1/jobs/{job_id}/results`
- `GET /api/v1/requests/{request_id}/export.csv`

## Sessies: van sessie 1 naar 3

### Sessie 1 — Foundation
- FastAPI-app + SQLite (werkt direct)
- Normalisatie naar E.164 (`+316...`)
- Basis lookup flow + UI
- Resultaatstructuur en request/result tabellen

### Sessie 2 — Multi-source + dedupe + confidence
- 4 bron-adapters actief:
  1. `phonenumbers_metadata`
  2. `numverify` (key-based)
  3. `serpapi` (key-based)
  4. `duckduckgo_search` (fallback)
- Cache met TTL (tijdelijke opslag van bronrespons)
- Scoring en deduplicatie

### Sessie 3 — Productielage
- Bulk endpoint + job tracking
- Resultaat exportendpoints
- Observability-ready velden (timestamps, status, audit op job/request)
- Klaar om PostgreSQL, Redis queue en worker toe te voegen

## Databronnen

- Gratis lokale bron:
  - `phonenumbers`: regio/carrier/tijdzone per nummer
- API-bron (sleutel nodig):
  - `NumVerify`: telefoonvalidatie + carrier/land/line type
  - `SerpAPI`: JSON-search op telefoonnummer (aanbevolen boven scraping)
- Web-bron (publiek):
  - `DuckDuckGo` HTML-search

## .env variabelen

- `NUMVERIFY_API_KEY` (aanbevolen)
- `SERPAPI_API_KEY` (alternatief in plaats van scraping)
- `DATABASE_URL` (standaard SQLite, wissel naar PostgreSQL bij productie)
- `DEFAULT_COUNTRY` (standaard NL)
- `CACHE_TTL_SECONDS`
- `MAX_BULK_ITEMS`

## Belangrijke beperking (praktisch)

Geen volledige “alle social media, alle accounts, alles op internet”-dekking in één request.  
Sommige platforms blokkeren scraping/zoeken of vereisen expliciete toestemming of API-toegang.
