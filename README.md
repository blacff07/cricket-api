```markdown
# Cricket API – Live Cricket Scores from Cricbuzz

A production‑ready Flask API that scrapes live cricket scores from Cricbuzz.  
Designed for easy deployment on **Vercel** and **Docker**. No API key required.

---

## Features

- **`/live-matches`** – List all currently live matches with their IDs
- **`/score?id=<match_id>`** – Detailed scorecard (batsmen, bowlers, run rate)
- **`/score/live?id=<match_id>`** – Same data wrapped in a `livescore` object
- Clean, modular code with Flask application factory pattern
- Configurable via environment variables
- Supports direct execution, Docker, and serverless deployment

---

## Tech Stack

- Python 3.11+
- Flask – Web framework
- BeautifulSoup4 / lxml – HTML parsing
- Requests – HTTP client
- Flask-CORS – Cross‑origin resource sharing
- Gunicorn – Production WSGI server (for Docker)
- Vercel – Serverless deployment

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

```bash
python -m app.main
```

The API will be available at http://localhost:5001

To change the port:

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

Or use Docker Compose

```bash
docker-compose up
```

The API will be available at http://localhost:5001

---

Deploy to Vercel

Step 1: Push your code to GitHub

Create a repository on GitHub and push your code:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/cricket-api.git
git push -u origin main
```

Step 2: Import your project on Vercel

1. Go to vercel.com
2. Click "Add New..." → "Project"
3. Import your GitHub repository
4. Vercel will automatically detect the Python configuration
5. Click "Deploy"

Step 3: Configure environment variables (optional)

If you need to change defaults, go to your project dashboard → Settings → Environment Variables and add:

Name Value Description
CORS_ORIGINS https://yourdomain.com Comma‑separated allowed origins

Step 4: Deploy

Vercel automatically deploys when you push to the main branch.
Your API will be available at https://cricket-api.vercel.app

---

Environment Variables

Variable Default Description
PORT 5001 Port for the app (set by Vercel automatically)
HOST 0.0.0.0 Host to bind to
CORS_ORIGINS http://localhost:5001,http://127.0.0.1:5001 Comma‑separated allowed origins

All variables are optional. No API keys required.

---

API Endpoints

GET /

```json
{
  "code": 200,
  "message": "Cricket API - Scrapes live data from Cricbuzz"
}
```

GET /live-matches

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

GET /score?id=139252

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

GET /score/live?id=139252

```json
{
  "success": "true",
  "livescore": {
    "title": "New Zealand vs Canada, 31st Match, Group D, ICC Men's T20 World Cup 2026",
    "update": "CAN opt to bat",
    "current": "CAN 70-0 (8.3)",
    "runrate": "CRR: 8.43",
    "batsman": "Dilpreet Bajwa",
    "batsmanrun": "28",
    "ballsfaced": "(29)",
    "sr": "96.55",
    "batsmantwo": "Yuvraj Samra",
    "batsmantworun": "39",
    "batsmantwoballfaced": "(22)",
    "batsmantwosr": "177.27",
    "bowler": "Cole McConchie",
    "bowlerover": "3",
    "bowlerruns": "20",
    "bowlerwickets": "0",
    "bowlereconomy": "6.66",
    "bowlertwo": "Kyle Jamieson",
    "bowlertwoover": "3",
    "bowlertworuns": "24",
    "bowlertwowickets": "0",
    "bowlertwoeconomy": "8.00"
  }
}
```

---

Project Structure

```
cricket-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # Flask app factory and routes
│   ├── scraper.py       # Scraping logic
│   ├── utils.py         # Helper functions
│   └── config.py        # Configuration
├── requirements.txt
├── vercel.json
├── Dockerfile
├── .dockerignore
├── .gitignore
├── README.md
└── docker-compose.yml
```

---

Testing the API

Get live matches

```bash
curl https://your-app.vercel.app/live-matches
```

Get score for a match

```bash
curl https://your-app.vercel.app/score?id=139252
```

Get formatted live score

```bash
curl https://your-app.vercel.app/score/live?id=139252
```

---

Troubleshooting

Common Vercel deployment issues

Issue Solution
"Module not found" Ensure requirements.txt includes all dependencies
Import errors Use relative imports (from .module import ...)
Timeout Increase timeout in config.py (default 10s)
CORS errors Set CORS_ORIGINS environment variable

Local development issues

Issue Solution
ImportError Run with python -m app.main not python app/main.py
Port already in use Change port with PORT=8080 python -m app.main
Missing logger Ensure import logging in all files that use logger

---

License

MIT

---

Author

Your Name – GitHub

---

Support

For issues or questions, please open an issue on GitHub.

```

## Vercel Hosting Steps (Plain Text)

1. **Push code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/cricket-api.git
   git push -u origin main
```

1. Go to Vercel (https://vercel.com)
   · Sign in with GitHub
   · Click "Add New" → "Project"
   · Select your repository
   · Click "Deploy" (no configuration needed)
2. Your API is live!
      URL: https://cricket-api.vercel.app
3. Test it
   ```bash
   curl https://cricket-api.vercel.app/live-matches
   ```

No environment variables needed. Just works.