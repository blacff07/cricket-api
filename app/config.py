import os
import time

class Config:
    # API version
    API_VERSION = "v1.0.0"

    # Start time for uptime tracking
    START_TIME = time.time()

    # Cricbuzz base URL
    CRICBUZZ_URL = "https://www.cricbuzz.com"

    # Request timeout in seconds
    REQUEST_TIMEOUT = 10

    # Cache TTL in seconds for different endpoints
    CACHE_TTL = 15  # For live matches list
    # (match detail endpoints use their own decorator with 5 seconds)

    # CORS allowed origins – update with your frontend domain(s)
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
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux i686; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ]

    # Host and port for local development
    HOST = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 5000))