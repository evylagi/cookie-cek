#!/usr/bin/env python3
"""
Flask API for Grok Cookie Checker
"""

import os
import json
import base64
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict, Any, Tuple
import requests

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

app = Flask(__name__)
CORS(app)


class GrokChecker:
    def __init__(self):
        self.required_cookies = ['sso', 'sso-rw']
        self.base_url = "https://grok.com"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            'host': 'grok.com',
            'user-agent': USER_AGENT,
            'accept': '*/*',
            'referer': 'https://grok.com/',
        }
    
    def decode_sso_token(self, token: str) -> Dict[str, Any]:
        try:
            parts = token.split('.')
            if len(parts) >= 2:
                payload = parts[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload)
                return json.loads(decoded)
        except:
            pass
        return {}
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'user': {},
            'session': {},
            'settings': {},
            'error': None
        }
        
        valid, missing = self.validate_required_cookies(cookies)
        if not valid:
            result['error'] = f"Missing cookies: {', '.join(missing)}"
            return False, result
        
        try:
            response = requests.get(
                f'{self.base_url}/api/auth/session',
                cookies=cookies,
                headers=self.get_headers(),
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'authenticated':
                    session = data.get('session', {})
                    
                    result['user'] = {
                        'id': session.get('userId', 'Unknown'),
                        'email': session.get('email', 'Unknown'),
                        'given_name': session.get('givenName', 'Unknown'),
                        'family_name': session.get('familyName', 'Unknown'),
                        'email_domain': session.get('emailDomain', 'Unknown'),
                        'x_user_id': session.get('xUserId', 'Not linked'),
                        'organization_id': session.get('organizationId', 'None'),
                        'organization_role': session.get('organizationRole', 'Unknown'),
                        'organization_type': session.get('organizationType', 'Unknown'),
                    }
                    
                    session_data = self.decode_sso_token(cookies.get('sso', ''))
                    result['session'] = {
                        'session_id': session_data.get('session_id', 'Unknown'),
                        'is_authenticated': True,
                    }
                    
                    result['settings'] = {
                        'device_id': cookies.get('grok_device_id', 'Unknown'),
                        'language': cookies.get('i18nextLng', 'en'),
                        'has_twitter_link': bool(cookies.get('_twpid')),
                    }
                    
                    return True, result
                else:
                    result['error'] = "Not authenticated"
                    return False, result
            elif response.status_code in [301, 302, 303, 307, 308]:
                result['error'] = "Redirected - cookies may be expired"
                return False, result
            elif response.status_code == 401:
                result['error'] = "Unauthorized - invalid or expired cookies"
                return False, result
            else:
                result['error'] = f"HTTP {response.status_code}"
                return False, result
                
        except requests.exceptions.Timeout:
            result['error'] = "Request timeout"
            return False, result
        except requests.exceptions.ConnectionError:
            result['error'] = "Connection error"
            return False, result
        except Exception as e:
            result['error'] = str(e)
            return False, result
    
    def validate_required_cookies(self, cookies: Dict[str, str]) -> Tuple[bool, list]:
        missing = [c for c in self.required_cookies if c not in cookies]
        return len(missing) == 0, missing


def parse_netscape_cookies(content: str) -> Dict[str, str]:
    cookies = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies


@app.route('/check', methods=['POST'])
def check_cookies():
    try:
        content = request.data.decode('utf-8')
        
        if not content or not content.strip():
            return jsonify({'success': False, 'error': 'Empty request body'}), 400
        
        cookies = parse_netscape_cookies(content)
        
        if not cookies:
            return jsonify({'success': False, 'error': 'No valid cookies found'}), 400
        
        checker = GrokChecker()
        valid, result = checker.check(cookies)
        
        return jsonify({
            'success': True,
            'valid': valid,
            'result': result,
            'cookies_found': len(cookies)
        })
        
    except UnicodeDecodeError:
        return jsonify({'success': False, 'error': 'Invalid encoding'}), 400
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'name': 'grok ni champo',
        'version': '1.0',
        'status': 'running'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=False)
