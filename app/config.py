import os

class Config:
    """Configuration class that reads from environment variables."""
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Server settings
    PORT = int(os.environ.get('PORT', 5001))
    HOST = os.environ.get('HOST', '0.0.0.0')

    # CORS allowed origins (comma‑separated list)
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5001,http://127.0.0.1:5001').split(',')

    # User agents for scraping (optional, defaults provided)
    USER_AGENTS = [
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
    ]

    # Cricbuzz base URL
    CRICBUZZ_URL = 'https://www.cricbuzz.com'

    # Timeout for requests to Cricbuzz (seconds)
    REQUEST_TIMEOUT = 10