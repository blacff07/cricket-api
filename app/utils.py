import logging
import sys
from flask import jsonify

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def json_error_response(message="Data not Found"):
    """Return a standard error JSON response."""
    return jsonify({
        'title': message,
        'update': message,
        'livescore': message,
        'runrate': message,
        'batterone': message,
        'batsmanonerun': message,
        'batsmanoneball': message,
        'batsmanonesr': message,
        'battertwo': message,
        'batsmantworun': message,
        'batsmantwoball': message,
        'batsmantwosr': message,
        'bowlerone': message,
        'bowleroneover': message,
        'bowleronerun': message,
        'bowleronewickers': message,
        'bowleroneeconomy': message,
        'bowlertwo': message,
        'bowlertwoover': message,
        'bowlertworun': message,
        'bowlertwowickers': message,
        'bowlertwoeconomy': message,
    })