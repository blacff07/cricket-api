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

def success_response(data=None, code=200, message=None):
    """Return a standardized success response."""
    response = {
        'success': True,
        'code': code,
        'data': data if data is not None else {}
    }
    if message:
        response['message'] = message
    return jsonify(response), code

def error_response(code=500, error_type='INTERNAL_ERROR', message='An unexpected error occurred'):
    """Return a standardized error response."""
    return jsonify({
        'success': False,
        'code': code,
        'error': {
            'type': error_type,
            'message': message
        }
    }), code

def json_error_response():
    """Legacy error response for backward compatibility."""
    return jsonify({
        'title': 'Data not Found',
        'update': 'Data not Found',
        'livescore': 'Data not Found',
        'runrate': 'Data not Found',
        'batterone': 'Data not Found',
        'batsmanonerun': 'Data not Found',
        'batsmanoneball': 'Data not Found',
        'batsmanonesr': 'Data not Found',
        'battertwo': 'Data not Found',
        'batsmantworun': 'Data not Found',
        'batsmantwoball': 'Data not Found',
        'batsmantwosr': 'Data not Found',
        'bowlerone': 'Data not Found',
        'bowleroneover': 'Data not Found',
        'bowleronerun': 'Data not Found',
        'bowleronewickers': 'Data not Found',
        'bowleroneeconomy': 'Data not Found',
        'bowlertwo': 'Data not Found',
        'bowlertwoover': 'Data not Found',
        'bowlertworun': 'Data not Found',
        'bowlertwowickers': 'Data not Found',
        'bowlertwoeconomy': 'Data not Found',
    })