import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from markupsafe import escape

from .config import Config
from .utils import setup_logging, json_error_response
from .scraper import fetch_page, extract_live_matches, extract_match_data

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure CORS
    CORS(app, origins=Config.CORS_ORIGINS)

    @app.route('/')
    def home():
        return jsonify({'code': 200, 'message': 'Cricket API - Scrapes live data from Cricbuzz'})

    @app.route('/live-matches', methods=['GET'])
    def live_matches():
        """Return all currently live matches."""
        url = f"{Config.CRICBUZZ_URL}/"
        soup = fetch_page(url)
        if soup is None:
            return jsonify({'matches': []})
        matches = extract_live_matches(soup)
        return jsonify({'matches': matches})

    @app.route('/score', methods=['GET'])
    def score():
        """Return detailed score for a specific match ID."""
        match_id = escape(request.args.get('id', ''))
        if not match_id:
            logger.warning("No match ID provided")
            return json_error_response()

        url = f"{Config.CRICBUZZ_URL}/live-cricket-scores/{match_id}"
        soup = fetch_page(url)
        if soup is None:
            return json_error_response()

        data = extract_match_data(soup)

        # Build response using the same keys as before
        batter_one = data['batsmen'][0] if data['batsmen'] else {}
        batter_two = data['batsmen'][1] if len(data['batsmen']) > 1 else {}
        bowler_one = data['bowlers'][0] if data['bowlers'] else {}
        bowler_two = data['bowlers'][1] if len(data['bowlers']) > 1 else {}

        return jsonify({
            'title': data['title'] or 'Data Not Found',
            'update': data['status'] or 'Data Not Found',
            'livescore': data['livescore'] or 'Data Not Found',
            'runrate': data['runrate'] or 'Data Not Found',
            'batterone': batter_one.get('name', 'Data Not Found'),
            'batsmanonerun': batter_one.get('runs', 'Data Not Found'),
            'batsmanoneball': f"({batter_one.get('balls', 'Data Not Found')})",
            'batsmanonesr': batter_one.get('sr', 'Data Not Found'),
            'battertwo': batter_two.get('name', 'Data Not Found'),
            'batsmantworun': batter_two.get('runs', 'Data Not Found'),
            'batsmantwoball': f"({batter_two.get('balls', 'Data Not Found')})",
            'batsmantwosr': batter_two.get('sr', 'Data Not Found'),
            'bowlerone': bowler_one.get('name', 'Data Not Found'),
            'bowleroneover': bowler_one.get('overs', 'Data Not Found'),
            'bowleronerun': bowler_one.get('runs', 'Data Not Found'),
            'bowleronewickers': bowler_one.get('wickets', 'Data Not Found'),
            'bowleroneeconomy': bowler_one.get('econ', 'Data Not Found'),
            'bowlertwo': bowler_two.get('name', 'Data Not Found'),
            'bowlertwoover': bowler_two.get('overs', 'Data Not Found'),
            'bowlertworun': bowler_two.get('runs', 'Data Not Found'),
            'bowlertwowickers': bowler_two.get('wickets', 'Data Not Found'),
            'bowlertwoeconomy': bowler_two.get('econ', 'Data Not Found')
        })

    @app.route('/score/live', methods=['GET'])
    def live():
        """Wrapper that returns the same data in a 'livescore' object."""
        data = score().get_json()
        if data['title'] != 'Data Not Found':
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
    @app.errorhandler(500)
    def handle_error(e):
        return json_error_response()

    return app

# For local development with `python app/main.py`
if __name__ == '__main__':
    app = create_app()
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)