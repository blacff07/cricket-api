import os
import time

class Config:
    """Configuration class that reads from environment variables."""
    
    # Server settings
    PORT = int(os.environ.get('PORT', 5001))
    HOST = os.environ.get('HOST', '0.0.0.0')
    
    # API version
    API_VERSION = 'v1.0.0'

    # CORS allowed origins (comma‑separated list)
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5001,http://127.0.0.1:5001').split(',')

    # User agents for scraping
    USER_AGENTS = [
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
    ]

    # Cricbuzz base URL
    CRICBUZZ_URL = 'https://www.cricbuzz.com'

    # Timeout for requests to Cricbuzz (seconds)
    REQUEST_TIMEOUT = 10
    
    # Cache TTL in seconds
    CACHE_TTL = 10
    
    # Start time for uptime calculation
    START_TIME = time.time()