import os
import time

class Config:
    # API version
    API_VERSION = "v1.0.0"

    # Start time for uptime tracking
    START_TIME = time.time()

    # Cricbuzz base URL
    CRICBUZZ_URL = "https://www.cricbuzz.com"

    # CORRECTED URLS
    LIVE_MATCHES_URL = f"{CRICBUZZ_URL}/cricket-match/live-scores"  # For match list
    SCORECARD_URL = f"{CRICBUZZ_URL}/live-cricket-scorecard"        # For match data (NOT /live-cricket-scores/)

    # Request timeout in seconds
    REQUEST_TIMEOUT = 10

    # Cache TTL in seconds for different endpoints
    CACHE_TTL = 15

    # CORS allowed origins
    CORS_ORIGINS = [
        "https://blac-cricket-api.vercel.app",
        "http://localhost:3000",
        "http://localhost:5000"
    ]

    # User agents for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]

    # Host and port for local development
    HOST = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 5000))