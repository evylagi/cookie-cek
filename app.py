"""
ChatGPT Session Checker API - Minimal Version
Only /gpt/check endpoint
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import os

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.environ.get('PORT', 10000))


def parse_netscape_cookies(cookie_text):
    """
    Parse Netscape format cookies into a dictionary
    """
    cookies = {}
    lines = cookie_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        
        parts = line.split('\t')
        if len(parts) >= 7:
            cookie_name = parts[5].strip()
            cookie_value = parts[6].strip()
            if cookie_name and cookie_value:
                cookies[cookie_name] = cookie_value
    
    return cookies


def get_account_details_from_html(html_content):
    """
    Extract account details from ChatGPT HTML response
    """
    account_details = {
        'plan_type': None,
        'user_id': None,
        'user_name': None,
        'user_email': None,
        'user_picture': None,
        'account_id': None,
        'structure': None,
        'is_fedramp': None,
        'is_delinquent': None,
        'residency_region': None,
        'access_token': None,
        'session_active': False,
        'session_expires': None,
        'auth_status': None
    }
    
    try:
        match = re.search(r'<script[^>]*id="client-bootstrap"[^>]*>(.*?)</script>', html_content, re.DOTALL)
        
        if not match:
            return account_details
            
        bootstrap_data = json.loads(match.group(1))
        
        session_data = bootstrap_data.get('session', {})
        account = session_data.get('account', {})
        user = session_data.get('user', {})
        
        account_details['plan_type'] = account.get('planType')
        account_details['account_id'] = account.get('id')
        account_details['structure'] = account.get('structure')
        account_details['is_fedramp'] = account.get('isFedrampCompliantWorkspace')
        account_details['is_delinquent'] = account.get('isDelinquent')
        account_details['residency_region'] = account.get('residencyRegion')
        account_details['session_expires'] = session_data.get('expires')
        account_details['user_id'] = user.get('id')
        account_details['user_name'] = user.get('name')
        account_details['user_email'] = user.get('email')
        account_details['user_picture'] = user.get('picture')
        
        access_token = session_data.get('accessToken')
        if access_token:
            account_details['access_token'] = access_token[:100] + '...' if len(access_token) > 100 else access_token
        
        account_details['session_active'] = bool(account.get('planType'))
        account_details['auth_status'] = bootstrap_data.get('authStatus')
        
        return account_details
        
    except Exception:
        return account_details


def check_chatgpt_session(cookie_dict):
    """
    Check if ChatGPT session is valid
    """
    headers = {
        'host': 'chatgpt.com',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'sec-fetch-site': 'cross-site',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-dest': 'document',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
    }
    
    html_content = ""
    account_details = {}
    
    try:
        response = requests.get('https://chatgpt.com', cookies=cookie_dict, headers=headers, timeout=10)
        html_content = response.text
        
        if response.status_code == 200:
            account_details = get_account_details_from_html(html_content)
            
            if account_details.get('plan_type'):
                return True, account_details, html_content
            
            session = requests.Session()
            session.cookies.update(cookie_dict)
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
                'accept': 'application/json',
            })
            resp = session.get('https://chatgpt.com/api/auth/session', timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('user'):
                    account_details['user_name'] = data.get('user', {}).get('name')
                    account_details['user_email'] = data.get('user', {}).get('email')
                    account_details['session_active'] = True
                    return True, account_details, html_content
                
        return False, account_details, html_content
        
    except Exception as e:
        return False, account_details, html_content


@app.route('/gpt/check', methods=['POST'])
def check_session():
    """
    Check ChatGPT session using provided cookies
    
    Request body:
    {
        "cookies": "Netscape format cookie string"
    }
    
    Response:
    {
        "success": true/false,
        "message": "Session is ACTIVE" or "Session is INACTIVE",
        "details": {
            "plan_type": "plus/free",
            "user_name": "John Doe",
            "user_email": "john@example.com",
            ...
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        cookie_text = data.get('cookies')
        
        if not cookie_text:
            return jsonify({
                'success': False,
                'error': 'Missing "cookies" field in request body'
            }), 400
        
        # Parse cookies
        cookies = parse_netscape_cookies(cookie_text)
        
        if not cookies:
            return jsonify({
                'success': False,
                'error': 'No valid cookies found in provided text'
            }), 400
        
        # Check session
        is_active, account_details, _ = check_chatgpt_session(cookies)
        
        if is_active:
            return jsonify({
                'success': True,
                'message': 'Session is ACTIVE',
                'details': account_details
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Session is INACTIVE or invalid',
                'details': account_details
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for Render
    """
    return jsonify({
        'status': 'healthy',
        'service': 'ChatGPT Session Checker API',
        'timestamp': str(datetime.utcnow())
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found. Available endpoints: POST /gpt/check, GET /health'
    }), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
