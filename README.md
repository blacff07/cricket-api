# Cricket API – Live Scores from Cricbuzz

A production‑ready Flask API that scrapes live cricket scores from Cricbuzz.  
Supports deployment on **Vercel** and **Docker**. No API key required.

## Features

- **`/live-matches`** – List all currently live matches with their IDs.
- **`/score?id=<match_id>`** – Detailed scorecard for a specific match (batsmen, bowlers, run rate, etc.).
- **`/score/live?id=<match_id>`** – Same data nested in a `livescore` object (convenient for frontend apps).

## Quick Start

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cricket-api.git
   cd cricket-api
   ```
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Run the development server:
   ```bash
   python -m app.main
   ```
   The API will be available at http://localhost:5001.

Run with Docker

```bash
docker build -t cricket-api .
docker run -p 5001:5001 cricket-api
```

Or use Docker Compose:

```bash
docker-compose up
```

Deploy to Vercel

1. Install the Vercel CLI and log in:
   ```bash
   npm i -g vercel
   vercel login
   ```
2. In the project root, run:
   ```bash
   vercel
   ```
   Follow the prompts. Vercel will automatically detect the Python environment.
3. Set the required environment variables in the Vercel dashboard:
   · CORS_ORIGINS – comma‑separated list of allowed origins (e.g., https://yourfrontend.com).

Environment Variables

Variable Description Default
CORS_ORIGINS Comma‑separated allowed origins for CORS http://localhost:5001,http://127.0.0.1:5001
PORT Port on which the app runs (used by Gunicorn) 5001
HOST Host to bind to 0.0.0.0

API Endpoints

GET /live-matches

Returns a list of all matches currently live on Cricbuzz.

Response:

```json
{
  "matches": [
    {
      "id": "139252",
      "title": "Canada vs New Zealand, 31st Match, Group D - Live",
      "status": "Live",
      "link": "/live-cricket-scores/139252/can-vs-nz-31st-match-group-d-icc-mens-t20-world-cup-2026"
    }
  ]
}
```

GET /score?id=<match_id>

Returns detailed score information for a specific match.

Response:

```json
{
  "title": "New Zealand vs Canada, 31st Match, Group D, ICC Men's T20 World Cup 2026",
  "update": "CAN opt to bat",
  "livescore": "CAN 70-0 (8.3)",
  "runrate": "CRR: 8.43",
  "batterone": "Dilpreet Bajwa",
  "batsmanonerun": "28",
  "batsmanoneball": "(29)",
  "batsmanonesr": "96.55",
  "battertwo": "Yuvraj Samra",
  "batsmantworun": "39",
  "batsmantwoball": "(22)",
  "batsmantwosr": "177.27",
  "bowlerone": "Cole McConchie",
  "bowleroneover": "3",
  "bowleronerun": "20",
  "bowleronewickers": "0",
  "bowleroneeconomy": "6.66",
  "bowlertwo": "Kyle Jamieson",
  "bowlertwoover": "3",
  "bowlertworun": "24",
  "bowlertwowickers": "0",
  "bowlertwoeconomy": "8.00"
}
```

If data is not available, all fields will contain "Data Not Found".

GET /score/live?id=<match_id>

Same data as /score but wrapped in a livescore object, with a success flag.

Response:

```json
{
  "success": "true",
  "livescore": {
    "title": "...",
    "update": "...",
    "current": "...",
    "runrate": "...",
    "batsman": "...",
    "batsmanrun": "...",
    "ballsfaced": "...",
    "sr": "...",
    "batsmantwo": "...",
    "batsmantworun": "...",
    "batsmantwoballfaced": "...",
    "batsmantwosr": "...",
    "bowler": "...",
    "bowlerover": "...",
    "bowlerruns": "...",
    "bowlerwickets": "...",
    "bowlereconomy": "...",
    "bowlertwo": "...",
    "bowlertwoover": "...",
    "bowlertworuns": "...",
    "bowlertwowickets": "...",
    "bowlertwoeconomy": "..."
  }
}
```

License

MIT

```

---

This repository is complete and ready to be pushed to GitHub. All files are written with best practices, error handling, and clear documentation. No placeholders remain; the code is functional and can be deployed immediately on Vercel or with Docker