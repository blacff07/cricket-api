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

setup_logging()
logger = logging.getLogger(__name__)

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

@lru_cache(maxsize=128)
def get_cached_start_time(match_id):
    url = f"{Config.CRICBUZZ_URL}/live-cricket-scorecard/{match_id}"
    soup, error = fetch_page(url)
    if soup is None:
        return None
    return extract_start_time_from_match_page(soup)

def enrich_matches_with_start_times(matches):
    match_ids = [m["id"] for m in matches]
    start_times = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_id = {executor.submit(get_cached_start_time, mid): mid for mid in match_ids}
        for future in as_completed(future_to_id):
            mid = future_to_id[future]
            try:
                start_times[mid] = future.result()
            except:
                start_times[mid] = None

    for match in matches:
        match["start_time"] = start_times.get(match["id"])

    return matches

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS)

    @app.route('/')
    def home():
        return success_response({
            "api_name": "Cricket API",
            "version": Config.API_VERSION,
            "endpoints": [
                "/health",
                "/live-matches",
                "/matches/{id}/live",
                "/matches/{id}/score",
                "/score?id={id}",
                "/score/live?id={id}"
            ]
        })

    @app.route('/health')
    def health():
        return success_response({
            "status": "ok",
            "uptime": int(time.time() - Config.START_TIME),
            "version": Config.API_VERSION,
            "timestamp": int(time.time())
        })

    @app.route('/live-matches')
    @cache_ttl(30)
    def live_matches():
        url = f"{Config.CRICBUZZ_URL}/cricket-match/live-scores"
        soup, error = fetch_page(url)

        if soup is None:
            return error_response(500, "SCRAPER_FAILED", "Failed to fetch live matches")

        matches = extract_live_matches(soup)
        matches = enrich_matches_with_start_times(matches)

        return success_response({"matches": matches})

    @app.route('/matches/<int:match_id>/live')
    @cache_ttl(5)
    def match_live(match_id):
        url = f"{Config.CRICBUZZ_URL}/live-cricket-scorecard/{match_id}"
        soup, error = fetch_page(url)

        if soup is None:
            return error_response(404, "MATCH_NOT_FOUND", f"No match found with id {match_id}")

        data = extract_match_data(soup)

        if not data.get("title"):
            return error_response(404, "MATCH_NOT_FOUND", f"No match found with id {match_id}")

        response_data = {
            "match_id": match_id,
            "title": data["title"],
            "teams": data.get("teams", []),
            "status": data["status"],
            "start_time": data.get("start_time"),
            "current_score": data.get("current_score"),
            "run_rate": data.get("run_rate"),
            "batting": data.get("batting", []),
            "bowling": data.get("bowling", [])
        }

        return success_response(response_data)

    @app.route('/matches/<int:match_id>/score')
    def match_score(match_id):
        return match_live(match_id)

    @app.route('/score')
    def score_legacy():
        match_id = escape(request.args.get("id", ""))
        if not match_id.isdigit():
            return json_error_response()

        return match_live(int(match_id))

    @app.route('/score/live')
    def score_live_legacy():
        match_id = escape(request.args.get("id", ""))
        if not match_id.isdigit():
            return json_error_response()

        return match_live(int(match_id))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=Config.HOST, port=Config.PORT, debug=True)