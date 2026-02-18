```markdown
# Cricket API – Live Cricket Scores from Cricbuzz

A production‑ready Flask API that scrapes live cricket scores from Cricbuzz.  
Designed for easy deployment on **Vercel** and **Docker**. No API key required.

---

## Features

- **`/live-matches`** – List all currently live matches with their IDs.
- **`/score?id=<match_id>`** – Detailed scorecard for a specific match (batsmen, bowlers, run rate, etc.).
- **`/score/live?id=<match_id>`** – Same data nested in a `livescore` object (convenient for frontend apps).
- Clean, modular code with Flask application factory pattern.
- Configurable via environment variables.
- Supports both direct execution and serverless deployment.

---

## Tech Stack

- **Python 3.11+**
- **Flask** – Web framework
- **BeautifulSoup4 / lxml** – HTML parsing
- **Requests** – HTTP client
- **Flask-CORS** – Cross‑origin resource sharing
- **Gunicorn** – Production WSGI server (for Docker)
- **Vercel** – Serverless deployment

---

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/cricket-api.git
cd cricket-api
```

2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Run the development server

You can start the app in two ways:

Using python -m (recommended for local development)

```bash
python -m app.main
```

Using Flask CLI

```bash
flask --app app.main:create_app run
```

The API will be available at http://localhost:5001 (default port).
To change the port, set the PORT environment variable:

```bash
PORT=8080 python -m app.main
```

---

Running with Docker

Build the image

```bash
docker build -t cricket-api .
```

Run the container

```bash
docker run -p 5001:5001 cricket-api
```

Or use Docker Compose:

```bash
docker-compose up
```

The API will be available at http://localhost:5001.

---

Deploy to Vercel

1. Install Vercel CLI and log in

```bash
npm i -g vercel
vercel login
```

2. Deploy

From the project root, run:

```bash
vercel
```

Follow the prompts. Vercel will automatically detect the Python configuration.

3. (Optional) Configure environment variables

If you need to change the default port or CORS origins, you can set them in the Vercel dashboard under Settings > Environment Variables:

· PORT – default 5001 (usually not needed, Vercel assigns its own)
· HOST – default 0.0.0.0
· CORS_ORIGINS – comma‑separated list, e.g., https://yourfrontend.com

---

Environment Variables

Variable Description Default
PORT Port on which the app runs (used by Gunicorn) 5001
HOST Host to bind to 0.0.0.0
CORS_ORIGINS Comma‑separated allowed origins for CORS http://localhost:5001,http://127.0.0.1:5001

All variables are optional. No secrets or API keys are required.

---

API Endpoints

GET /

Returns a simple welcome message.

Response:

```json
{
  "code": 200,
  "message": "Cricket API - Scrapes live data from Cricbuzz"
}
```

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

Response (successful):

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

Response (failure):

```json
{
  "success": "false",
  "livescore": {}
}
```

---

Project Structure

```
cricket-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # Flask app factory and routes
│   ├── scraper.py       # Scraping logic (Cricbuzz)
│   ├── utils.py         # Helper functions (logging, error responses)
│   └── config.py        # Configuration from environment variables
├── requirements.txt
├── vercel.json
├── Dockerfile
├── .dockerignore
├── .gitignore
├── README.md
└── docker-compose.yml   (optional, for local development)
```

---

License

MIT

```