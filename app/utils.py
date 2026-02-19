import logging
from flask import jsonify

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def success_response(data, code=200, message=None):
    """Standard success response wrapper."""
    response = {
        "success": True,
        "code": code,
        "data": data
    }
    if message:
        response["message"] = message
    return jsonify(response), code

def error_response(code, error_type, message):
    """Standard error response wrapper."""
    return jsonify({
        "success": False,
        "code": code,
        "error": error_type,
        "message": message
    }), code

def json_error_response():
    """Legacy error response for /score endpoint."""
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