#!/usr/bin/env python3
"""
2Captcha Cookie Checker API Server
Hosted on Render.com
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import re
import requests
from datetime import datetime
from typing import Dict, Any

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

class TwoCaptchaChecker:
    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
        
    def check_session(self) -> Dict[str, Any]:
        """Check 2Captcha session validity"""
        try:
            headers = {
                'host': '2captcha.com',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                'referer': 'https://2captcha.com/',
                'accept-language': 'en-US,en;q=0.9',
            }
            
            response = requests.get(
                'https://2captcha.com/enterpage',
                cookies=self.cookies,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                user_info = self._extract_user_info(response.text)
                if user_info.get('user_id'):
                    return {
                        'status': 'valid',
                        'message': '2Captcha session valid',
                        'user_info': user_info,
                        'status_code': response.status_code
                    }
                elif 'initialGlobalState' in response.text:
                    return {
                        'status': 'valid',
                        'message': '2Captcha session appears valid',
                        'status_code': response.status_code
                    }
            
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('Location', '')
                if 'login' in location or 'sign-in' in location:
                    return {
                        'status': 'invalid',
                        'message': 'Session expired. Redirected to login.',
                        'status_code': response.status_code
                    }
            
            return {
                'status': 'unknown',
                'message': f'Unexpected response: {response.status_code}',
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Request failed: {str(e)}'
            }
    
    def _extract_user_info(self, html: str) -> Dict[str, Any]:
        """Extract user info from HTML"""
        user_info = {}
        
        # Extract user ID
        id_match = re.search(r'"id":(\d+)', html)
        if id_match:
            user_info['user_id'] = id_match.group(1)
        
        # Extract email
        email_match = re.search(r'"address":"([^"]+@[^"]+)"', html)
        if not email_match:
            email_match = re.search(r'"email":"([^"]+@[^"]+)"', html)
        if email_match:
            user_info['email'] = email_match.group(1)
        
        # Extract balance
        balance_match = re.search(r'"amount":([\d.]+)', html)
        if balance_match:
            user_info['balance'] = balance_match.group(1)
        
        return user_info


@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return jsonify({
        'service': '2Captcha Cookie Checker API',
        'version': '1.0.0',
        'endpoints': {
            '/api/health': 'GET - Health check',
            '/api/check-2captcha': 'POST - Check 2Captcha cookies'
        },
        'status': 'running'
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/check-2captcha', methods=['POST'])
def check_2captcha():
    """API endpoint to check 2Captcha cookies"""
    try:
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing cookies parameter'
            }), 400
        
        cookies = data['cookies']
        checker = TwoCaptchaChecker(cookies)
        result = checker.check_session()
        
        return jsonify({
            'status': 'success',
            'data': result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)