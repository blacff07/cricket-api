import logging
import time
from functools import wraps, lru_cache
from flask import Flask, jsonify, request
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config
from .utils import setup_logging, success_response, error_response
from .scraper import fetch_page, extract_live_matches, extract_start_time_from_match_page

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Simple in-memory cache
def cache_ttl(seconds=Config.CACHE_TTL):
    def decorator(func):
        cache = {}
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            if key in cache:
                result, timestamp = cache[key]
                if time.time() - timestamp < seconds:
                    return result
            result = func(*args, **kwargs)
            cache[key] = (result, time.time())
            return result
        return wrapper
    return decorator

# Cache for start times per match ID
@lru_cache(maxsize=128)
def get_cached_start_time(match_id):
    """Fetch and cache start time for a single match."""
    url = f"{Config.CRICBUZZ_URL}/live-cricket-scores/{match_id}"
    soup, error = fetch_page(url)
    if soup is None:
        logger.warning(f"Failed to fetch start time for match {match_id}: {error}")
        return None
    return extract_start_time_from_match_page(soup)

def enrich_matches_with_start_times(matches):
    """Enrich a list of matches with start times fetched concurrently."""
    match_ids = [m['id'] for m in matches]
    start_times = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_id = {executor.submit(get_cached_start_time, mid): mid for mid in match_ids}
        for future in as_completed(future_to_id):
            mid = future_to_id[future]
            try:
                start_times[mid] = future.result()
            except Exception as e:
                logger.error(f"Error fetching start time for match {mid}: {e}")
                start_times[mid] = None
    for match in matches:
        match['start_time'] = start_times.get(match['id'])
    return matches

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS)

    @app.route('/')
    def home():
        return success_response({
            'api_name': 'Cricket API',
            'version': Config.API_VERSION,
            'endpoints': [
                '/health',
                '/live-matches',
                '/matches/{id}/live',
                '/matches/{id}/score'
            ]
        }, message='Cricket API - Scrapes live data from Cricbuzz')

    @app.route('/health')
    def health():
        return success_response({
            'status': 'ok',
            'uptime': int(time.time() - Config.START_TIME),
            'version': Config.API_VERSION,
            'timestamp': int(time.time())
        })

    @app.route('/live-matches', methods=['GET'])
    @cache_ttl(30)
    def live_matches():
        """Return all currently live matches with start times."""
        url = f"{Config.CRICBUZZ_URL}/"
        soup, error = fetch_page(url)
        if soup is None:
            if error == "timeout":
                return error_response(503, 'SERVICE_UNAVAILABLE', 'Cricbuzz is not responding')
            elif error == "connection_error":
                return error_response(503, 'SERVICE_UNAVAILABLE', 'Cannot connect to Cricbuzz')
            else:
                return error_response(500, 'SCRAPER_FAILED', 'Failed to fetch live matches')
        
        matches = extract_live_matches(soup)
        matches = enrich_matches_with_start_times(matches)
        
        clean_matches = []
        for m in matches:
            clean_matches.append({
                'id': m['id'],
                'teams': m.get('teams', []),
                'title': m['title'],
                'status': m['status'],
                'start_time': m.get('start_time')
            })
        return success_response({'matches': clean_matches})

    @app.route('/matches/<int:match_id>/live', methods=['GET'])
    @cache_ttl(5)
    def match_live(match_id):
        """Return live score for a specific match."""
        url = f"{Config.CRICBUZZ_URL}/live-cricket-scores/{match_id}"
        soup, error = fetch_page(url)
        if soup is None:
            if error == "timeout":
                return error_response(503, 'SERVICE_UNAVAILABLE', 'Cricbuzz is not responding')
            elif error == "connection_error":
                return error_response(503, 'SERVICE_UNAVAILABLE', 'Cannot connect to Cricbuzz')
            elif error == "http_404":
                return error_response(404, 'MATCH_NOT_FOUND', f'No match found with id {match_id}')
            else:
                return error_response(500, 'SCRAPER_FAILED', 'Failed to fetch match data')

        from .scraper import extract_match_data
        data = extract_match_data(soup)

        if not data.get('title'):
            return error_response(404, 'MATCH_NOT_FOUND', f'No match found with id {match_id}')

        response_data = {
            'match_id': match_id,
            'title': data['title'],
            'teams': data.get('teams', []),
            'status': data['status'],
            'start_time': data.get('start_time'),
            'current_score': data.get('current_score'),
            'run_rate': data.get('run_rate'),
            'batting': data.get('batting', []),
            'bowling': data.get('bowling', [])
        }
        return success_response(response_data)

    @app.route('/matches/<int:match_id>/score', methods=['GET'])
    @cache_ttl(5)
    def match_score(match_id):
        """Return detailed scorecard for a specific match."""
        return match_live(match_id)

    @app.errorhandler(404)
    def not_found(e):
        return error_response(404, 'NOT_FOUND', 'Endpoint not found')

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}")
        return error_response(500, 'INTERNAL_ERROR', 'An unexpected error occurred')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=Config.HOST, port=Config.PORT, debug=True)