import logging
import time
from functools import wraps
from functools import lru_cache
from flask import Flask, jsonify, request
from flask_cors import CORS
from markupsafe import escape

from .config import Config
from .utils import setup_logging, success_response, error_response, json_error_response
from .scraper import fetch_page, extract_live_matches, extract_match_data

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Simple in-memory cache with proper function name preservation
def cache_ttl(seconds=Config.CACHE_TTL):
    def decorator(func):
        cache = {}
        @wraps(func)  # This preserves the original function name
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

def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure CORS
    CORS(app, origins=Config.CORS_ORIGINS)

    @app.route('/')
    def home():
        return success_response({
            'api_name': 'Cricket API',
            'version': Config.API_VERSION,
            'endpoints': [
                '/api/v1/health',
                '/api/v1/live-matches',
                '/api/v1/matches/{id}/live',
                '/api/v1/matches/{id}/score'
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

    # API v1 endpoints
    @app.route('/api/v1/health')
    def v1_health():
        return health()

    @app.route('/api/v1/live-matches', methods=['GET'])
    @cache_ttl(15)
    def v1_live_matches():
        """Return all currently live matches."""
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
        return success_response({'matches': matches})

    @app.route('/api/v1/matches/<int:match_id>/live', methods=['GET'])
    @cache_ttl(5)
    def v1_match_live(match_id):
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
        
        if not data['title']:
            return error_response(404, 'MATCH_NOT_FOUND', f'No match found with id {match_id}')

        return success_response({
            'match_id': match_id,
            'title': data['title'],
            'series': data['series'],
            'teams': data['teams'],
            'status': data['status'],
            'match_state': data['match_state'],
            'current_score': data['current_score'],
            'run_rate': data['run_rate'],
            'batting': data['batting'],
            'bowling': data['bowling'][:2]  # Only current bowlers
        })

    @app.route('/api/v1/matches/<int:match_id>/score', methods=['GET'])
    @cache_ttl(5)
    def v1_match_score(match_id):
        """Return detailed scorecard for a specific match."""
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
        
        if not data['title']:
            return error_response(404, 'MATCH_NOT_FOUND', f'No match found with id {match_id}')

        return success_response({
            'match_id': match_id,
            'title': data['title'],
            'series': data['series'],
            'teams': data['teams'],
            'status': data['status'],
            'match_state': data['match_state'],
            'current_score': data['current_score'],
            'run_rate': data['run_rate'],
            'batting': data['batting'],
            'bowling': data['bowling']
        })

    # Legacy endpoints (for backward compatibility)
    @app.route('/live-matches', methods=['GET'])
    def live_matches_legacy():
        data = v1_live_matches().get_json()
        if data.get('success'):
            return jsonify({'matches': data['data']['matches']})
        return jsonify({'matches': []})

    @app.route('/score', methods=['GET'])
    def score_legacy():
        match_id = escape(request.args.get('id', ''))
        if not match_id:
            return json_error_response()
        
        try:
            match_id_int = int(match_id)
            response = v1_match_score(match_id_int)
            data = response.get_json()
            
            if data.get('success'):
                d = data['data']
                # Convert back to legacy format
                batting = d.get('batting', [])
                bowling = d.get('bowling', [])
                
                batter_one = batting[0] if len(batting) > 0 else {}
                batter_two = batting[1] if len(batting) > 1 else {}
                bowler_one = bowling[0] if len(bowling) > 0 else {}
                bowler_two = bowling[1] if len(bowling) > 1 else {}
                
                current = d.get('current_score', {})
                livescore = f"{current.get('team', '')} {current.get('runs', 0)}-{current.get('wickets', 0)} ({current.get('overs', 0)})" if current else 'Data Not Found'
                
                return jsonify({
                    'title': d.get('title', 'Data Not Found'),
                    'update': d.get('status', 'Data Not Found'),
                    'livescore': livescore,
                    'runrate': f"CRR: {d.get('run_rate', 'Data Not Found')}" if d.get('run_rate') else 'Data Not Found',
                    'batterone': batter_one.get('name', 'Data Not Found'),
                    'batsmanonerun': str(batter_one.get('runs', 'Data Not Found')),
                    'batsmanoneball': f"({batter_one.get('balls', 'Data Not Found')})",
                    'batsmanonesr': str(batter_one.get('sr', 'Data Not Found')),
                    'battertwo': batter_two.get('name', 'Data Not Found'),
                    'batsmantworun': str(batter_two.get('runs', 'Data Not Found')),
                    'batsmantwoball': f"({batter_two.get('balls', 'Data Not Found')})",
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
            else:
                return json_error_response()
        except (ValueError, TypeError):
            return json_error_response()

    @app.route('/score/live', methods=['GET'])
    def live_legacy():
        data = score_legacy().get_json()
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

# For local development with `python -m app.main`
if __name__ == '__main__':
    app = create_app()
    app.run(host=Config.HOST, port=Config.PORT, debug=True)