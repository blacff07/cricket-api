import os
import time

class Config:
    API_VERSION = "v1.0.0"
    START_TIME = time.time()

    CRICBUZZ_URL = "https://www.cricbuzz.com"
    REQUEST_TIMEOUT = 12
    CACHE_TTL = 15

    CORS_ORIGINS = [
        "https://blac-cricket-api.vercel.app",
        "http://localhost:3000",
        "http://localhost:5000"
    ]

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]

    HOST = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 5000))