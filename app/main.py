import logging
import time
from functools import wraps, lru_cache
from flask import Flask, jsonify, request
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor, as_completed
from markupsafe import escape

from .config import Config
from .utils import setup_logging, success_response, error_response, json_error_response
from .scraper import (
    fetch_page,
    extract_live_matches,
    extract_start_time_from_match_page,
    extract_match_data
)

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
                '/matches/{id}/score',
                '/score?id={id} (legacy)',
                '/score/live?id={id} (legacy)'
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

    # ------------------------------------------------------------------
    # Legacy endpoints (FIXED - now use scraper directly)
    # ------------------------------------------------------------------
    @app.route('/score', methods=['GET'])
    def score_legacy():
        match_id = escape(request.args.get('id', ''))
        if not match_id:
            return json_error_response()

        try:
            match_id_int = int(match_id)
        except ValueError:
            return json_error_response()

        # Fetch the match page directly using the scraper
        url = f"{Config.CRICBUZZ_URL}/live-cricket-scores/{match_id_int}"
        soup, error = fetch_page(url)
        
        # Fallback response when data cannot be fetched
        def fallback_response():
            return jsonify({
                'title': 'Data Not Found',
                'update': 'Data Not Found',
                'livescore': 'Data Not Found',
                'runrate': 'Data Not Found',
                'batterone': 'Data Not Found',
                'batsmanonerun': 'Data Not Found',
                'batsmanoneball': 'Data Not Found',
                'batsmanonesr': 'Data Not Found',
                'battertwo': 'Data Not Found',
                'batsmantworun': 'Data Not Found',
                'batsmantwoball': 'Data Not Found',
                'batsmantwosr': 'Data Not Found',
                'bowlerone': 'Data Not Found',
                'bowleroneover': 'Data Not Found',
                'bowleronerun': 'Data Not Found',
                'bowleronewickers': 'Data Not Found',
                'bowleroneeconomy': 'Data Not Found',
                'bowlertwo': 'Data Not Found',
                'bowlertwoover': 'Data Not Found',
                'bowlertworun': 'Data Not Found',
                'bowlertwowickers': 'Data Not Found',
                'bowlertwoeconomy': 'Data Not Found'
            })

        if soup is None:
            logger.error(f"Failed to fetch page for match {match_id_int}: {error}")
            return fallback_response()

        data = extract_match_data(soup)
        if not data.get('title'):
            logger.warning(f"No title found for match {match_id_int}")
            return fallback_response()

        # Format legacy response
        batting = data.get('batting', [])
        bowling = data.get('bowling', [])
        
        # Take first two batsmen/bowlers for legacy format
        batter_one = batting[0] if len(batting) > 0 else {}
        batter_two = batting[1] if len(batting) > 1 else {}
        bowler_one = bowling[0] if len(bowling) > 0 else {}
        bowler_two = bowling[1] if len(bowling) > 1 else {}
        
        current = data.get('current_score', {})
        livescore = f"{current.get('team', '')} {current.get('runs', 0)}-{current.get('wickets', 0)} ({current.get('overs', 0)})" if current else 'Data Not Found'
        run_rate_val = data.get('run_rate')
        runrate_str = f"CRR: {run_rate_val}" if run_rate_val is not None else 'Data Not Found'

        return jsonify({
            'title': data.get('title', 'Data Not Found'),
            'update': data.get('status', 'Data Not Found'),
            'livescore': livescore,
            'runrate': runrate_str,
            'batterone': batter_one.get('name', 'Data Not Found'),
            'batsmanonerun': str(batter_one.get('runs', 'Data Not Found')),
            'batsmanoneball': f"({batter_one.get('balls', 'Data Not Found')})" if batter_one.get('balls') is not None else 'Data Not Found',
            'batsmanonesr': str(batter_one.get('sr', 'Data Not Found')),
            'battertwo': batter_two.get('name', 'Data Not Found'),
            'batsmantworun': str(batter_two.get('runs', 'Data Not Found')),
            'batsmantwoball': f"({batter_two.get('balls', 'Data Not Found')})" if batter_two.get('balls') is not None else 'Data Not Found',
            'batsmantwosr': str(batter_two.get('sr', 'Data Not Found')),
            'bowlerone': bowler_one.get('name', 'Data Not Found'),
            'bowleroneover': str(bowler_one.get('overs', 'Data Not Found')),
            'bowleronerun': str(bowler_one.get('runs', 'Data Not Found')),
            'bowleronewickers': str(bowler_one.get('wickets', 'Data Not Found')),
            'bowleroneeconomy': str(bowler_one.get('econ', 'Data Not Found')),
            'bowlertwo': bowler_two.get('name', 'Data Not Found'),
            'bowlertwoover': str(bowler_two.get('overs', 'Data Not Found')),
            'bowlertworun': str(bowler_two.get('runs', 'Data Not Found')),
            'bowlertwowickers': str(bowler_two.get('wickets', 'Data Not Found')),
            'bowlertwoeconomy': str(bowler_two.get('econ', 'Data Not Found'))
        })

    @app.route('/score/live', methods=['GET'])
    def live_legacy():
        match_id = escape(request.args.get('id', ''))
        if not match_id:
            return json_error_response()
            
        try:
            match_id_int = int(match_id)
        except ValueError:
            return json_error_response()

        # Get the flat response from score_legacy
        resp = score_legacy()
        data = resp.get_json()
        
        if data.get('title') != 'Data Not Found':
            return jsonify({
                'success': 'true',
                'livescore': {
                    'title': data['title'],
                    'update': data['update'],
                    'current': data['livescore'],
                    'runrate': data['runrate'],
                    'batsman': data['batterone'],
                    'batsmanrun': data['batsmanonerun'],
                    'ballsfaced': data['batsmanoneball'],
                    'sr': data['batsmanonesr'],
                    'batsmantwo': data['battertwo'],
                    'batsmantworun': data['batsmantworun'],
                    'batsmantwoballfaced': data['batsmantwoball'],
                    'batsmantwosr': data['batsmantwosr'],
                    'bowler': data['bowlerone'],
                    'bowlerover': data['bowleroneover'],
                    'bowlerruns': data['bowleronerun'],
                    'bowlerwickets': data['bowleronewickers'],
                    'bowlereconomy': data['bowleroneeconomy'],
                    'bowlertwo': data['bowlertwo'],
                    'bowlertwoover': data['bowlertwoover'],
                    'bowlertworuns': data['bowlertworun'],
                    'bowlertwowickets': data['bowlertwowickers'],
                    'bowlertwoeconomy': data['bowlertwoeconomy']
                }
            })
        else:
            return jsonify({'success': 'false', 'livescore': {}})

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