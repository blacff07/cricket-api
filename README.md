# Cricket API

A production‑ready API that scrapes live cricket data from Cricbuzz.  
Returns clean JSON for live matches, scorecards, and player statistics – compatible with Telegram bots and other applications.

## Features

- **Live matches** – list of all currently live/upcoming/completed matches.
- **Match score** – detailed scorecard for a given match ID.
- **Lightning fast** – in‑memory caching reduces load on Cricbuzz.
- **No environment variables** – everything is hardcoded; deploy anywhere.
- **Professional error handling** – graceful degradation with meaningful error messages.
- **CORS enabled** – can be called from any frontend.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information and available endpoints. |
| `/health` | GET | Health check with uptime and version. |
| `/live-matches` | GET | Returns a list of all matches (live, upcoming, completed). |
| `/score?id={match_id}` | GET | Returns legacy score format (used by older bots). |
| `/score/live?id={match_id}` | GET | Returns detailed live score in a structured format. |

### Example Requests

```bash
curl https://your-domain.vercel.app/live-matches
curl https://your-domain.vercel.app/score?id=139318
curl https://your-domain.vercel.app/score/live?id=139318
```

Deployment

1. Vercel (Recommended)

· Push this repository to GitHub.
· Import the project on Vercel.
· No environment variables needed – just deploy.

2. Docker

```bash
docker build -t cricket-api .
docker run -p 8000:8000 cricket-api
```

Or using docker‑compose:

```bash
docker-compose up -d
```

3. VPS / Bare Metal

· Install Python 3.11+ and pip.
· Clone the repository.
· Install dependencies: pip install -r requirements.txt
· Run with Gunicorn: gunicorn wsgi:app --bind 0.0.0.0:8000

Project Structure

```
cricket-api/
├── app/                # Application package
│   ├── __init__.py
│   ├── config.py       # Configuration (hardcoded)
│   ├── main.py         # Flask app and routes
│   ├── scraper.py      # Web scraping logic
│   └── utils.py        # Helpers (logging, responses)
├── wsgi.py             # Entry point for WSGI servers
├── vercel.json         # Vercel deployment config
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container definition
├── docker-compose.yml  # Compose for local development
├── .gitignore          # Standard Python gitignore
└── README.md           # This file
```

Caching

Responses are cached for 15 seconds (live matches) and 5 seconds (score endpoints) to reduce the load on Cricbuzz and improve response times.

Error Handling

All errors return a consistent JSON structure:

```json
{
  "success": false,
  "code": 404,
  "error": "NOT_FOUND",
  "message": "No match found with id 12345"
}
```

License

MIT – feel free to use and modify.
```
Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```