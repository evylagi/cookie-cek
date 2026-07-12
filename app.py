#!/usr/bin/env python3
"""
Flask API for Multi-Platform Cookie Checker
Supports: Grok, ChatGPT, Claude AI, TikTok, Netflix
"""

import os
import json
import base64
import re
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

REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

app = Flask(__name__)
CORS(app)


class BaseChecker:
    def __init__(self):
        self.required_cookies = []
        self.name = "Unknown"
    
    def validate_required_cookies(self, cookies: Dict[str, str]) -> Tuple[bool, list]:
        missing = [c for c in self.required_cookies if c not in cookies]
        return len(missing) == 0, missing


class GrokChecker(BaseChecker):
    def __init__(self):
        super().__init__()
        self.name = "Grok"
        self.required_cookies = ['sso', 'sso-rw']
        self.base_url = "https://grok.com"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            'host': 'grok.com',
            'sec-ch-ua-platform': '"Windows"',
            'user-agent': USER_AGENT,
            'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'accept': '*/*',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://grok.com/',
            'accept-language': 'en-US,en;q=0.9',
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
                try:
                    data = response.json()
                except:
                    result['error'] = "Invalid JSON response"
                    return False, result
                
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


class ChatGPTChecker(BaseChecker):
    def __init__(self):
        super().__init__()
        self.name = "ChatGPT"
        self.required_cookies = ['oai-client-auth-info']
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'user': {},
            'plan': {},
            'session': {},
            'location': {},
            'error': None
        }
        
        valid, missing = self.validate_required_cookies(cookies)
        if not valid:
            result['error'] = f"Missing cookies: {', '.join(missing)}"
            return False, result
        
        try:
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://chatgpt.com/',
                'Origin': 'https://chatgpt.com',
            }
            
            session = requests.Session()
            session.cookies.update(cookies)
            
            # Try to get session info
            response = session.get(
                'https://chatgpt.com/api/auth/session',
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    result['error'] = "Invalid JSON response from ChatGPT API"
                    return False, result
                
                if data and data.get('user'):
                    user = data.get('user', {})
                    result['user'] = {
                        'id': user.get('id', 'Unknown'),
                        'name': user.get('name', 'Unknown'),
                        'email': user.get('email', 'Unknown'),
                        'picture': user.get('picture'),
                    }
                    
                    result['session'] = {
                        'expires': data.get('expires'),
                        'access_token': data.get('accessToken', '')[:50] + '...' if data.get('accessToken') else None,
                    }
                    
                    # Try to get plan info
                    try:
                        plan_response = session.get(
                            'https://chatgpt.com/api/accounts',
                            headers=headers,
                            timeout=10
                        )
                        if plan_response.status_code == 200:
                            try:
                                plan_data = plan_response.json()
                                if plan_data and len(plan_data) > 0:
                                    account = plan_data[0]
                                    result['plan'] = {
                                        'type': account.get('planType', 'Unknown'),
                                        'structure': account.get('structure', 'Unknown'),
                                    }
                            except:
                                pass
                    except:
                        pass
                    
                    return True, result
                else:
                    result['error'] = "Not authenticated - session expired"
                    return False, result
            elif response.status_code == 401:
                result['error'] = "Unauthorized - cookies expired or invalid"
                return False, result
            elif response.status_code == 403:
                result['error'] = "Forbidden - access denied"
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


class ClaudeChecker(BaseChecker):
    def __init__(self):
        super().__init__()
        self.name = "Claude AI"
        self.required_cookies = ['sessionKey', 'routingHint']
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'user': {},
            'org': {},
            'plan': {},
            'error': None
        }
        
        valid, missing = self.validate_required_cookies(cookies)
        if not valid:
            result['error'] = f"Missing cookies: {', '.join(missing)}"
            return False, result
        
        try:
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'application/json',
                'anthropic-device-id': cookies.get('anthropic-device-id', ''),
                'anthropic-client-platform': 'web_claude_ai',
            }
            
            org_uuid = cookies.get('lastActiveOrg', '')
            if not org_uuid:
                result['error'] = "No organization UUID found in cookies"
                return False, result
            
            response = requests.get(
                f'https://claude.ai/edge-api/bootstrap/{org_uuid}/app_start',
                cookies=cookies,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    result['error'] = "Invalid JSON response from Claude API"
                    return False, result
                
                account = data.get('account', {})
                
                result['user'] = {
                    'uuid': account.get('uuid'),
                    'name': account.get('display_name', 'Unknown'),
                    'full_name': account.get('full_name', 'Unknown'),
                    'email': account.get('email_address', 'Unknown'),
                    'verified': account.get('is_verified', False),
                }
                
                memberships = account.get('memberships', [])
                if memberships:
                    membership = memberships[0]
                    org = membership.get('organization', {})
                    result['org'] = {
                        'uuid': org.get('uuid'),
                        'name': org.get('name', 'Unknown'),
                        'role': membership.get('role', 'Unknown'),
                    }
                
                # Try to get plan
                try:
                    plan_response = requests.get(
                        f'https://claude.ai/api/organizations/{org_uuid}/paused_subscription_details',
                        cookies=cookies,
                        headers=headers,
                        timeout=10
                    )
                    if plan_response.status_code == 200:
                        try:
                            plan_data = plan_response.json()
                            result['plan'] = {
                                'type': plan_data.get('plan_type', 'free'),
                            }
                        except:
                            pass
                except:
                    pass
                
                return True, result
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


class TikTokChecker(BaseChecker):
    def __init__(self):
        super().__init__()
        self.name = "TikTok"
        self.required_cookies = ['sessionid', 'sid_tt']
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'user': {},
            'stats': {},
            'error': None
        }
        
        valid, missing = self.validate_required_cookies(cookies)
        if not valid:
            result['error'] = f"Missing cookies: {', '.join(missing)}"
            return False, result
        
        try:
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'application/json',
                'Referer': 'https://www.tiktok.com/'
            }
            
            response = requests.get(
                'https://www.tiktok.com/passport/web/account/info/',
                params={'aid': '1459', 'user_is_login': 'true'},
                cookies=cookies,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    result['error'] = "Invalid JSON response from TikTok API"
                    return False, result
                
                if data.get('message') == 'success':
                    account = data.get('data', {})
                    result['user'] = {
                        'username': account.get('username', 'Unknown'),
                        'user_id': account.get('user_id_str', 'Unknown'),
                        'display_name': account.get('screen_name', 'Unknown'),
                        'email': account.get('email', 'Unknown'),
                        'verified': account.get('verified', False),
                        'private': account.get('private', False),
                    }
                    return True, result
                else:
                    result['error'] = data.get('message', 'Unknown error')
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


class NetflixChecker(BaseChecker):
    def __init__(self):
        super().__init__()
        self.name = "Netflix"
        self.required_cookies = ['NetflixId', 'SecureNetflixId']
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'user': {},
            'plan': {},
            'account': {},
            'error': None
        }
        
        valid, missing = self.validate_required_cookies(cookies)
        if not valid:
            result['error'] = f"Missing cookies: {', '.join(missing)}"
            return False, result
        
        try:
            session = requests.Session()
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='.netflix.com', path='/')
            
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html',
                'Referer': 'https://www.netflix.com/'
            }
            session.headers.update(headers)
            
            response = session.get('https://www.netflix.com/YourAccount', timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                result['error'] = f"HTTP {response.status_code}"
                return False, result
            
            html = response.text
            
            if 'login' in response.url.lower() or '"mode":"login"' in html:
                result['error'] = "Not logged in - cookies expired"
                return False, result
            
            info = {}
            
            email_match = re.search(r'"email":"([^"]+)"', html)
            if email_match:
                info['email'] = email_match.group(1)
            
            name_match = re.search(r'"firstName":"([^"]+)"', html)
            if name_match:
                info['name'] = name_match.group(1)
            
            plan_match = re.search(r'"planName":"([^"]+)"', html)
            if plan_match:
                info['plan'] = plan_match.group(1)
            
            if info:
                result['user'] = {
                    'name': info.get('name', 'Unknown'),
                    'email': info.get('email', 'Unknown'),
                }
                result['plan'] = {
                    'type': info.get('plan', 'Unknown'),
                }
                result['account'] = {
                    'status': 'Active',
                }
                return True, result
            else:
                result['error'] = "Failed to extract account information"
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


def detect_platform(cookies: Dict[str, str]) -> str:
    if 'NetflixId' in cookies and 'SecureNetflixId' in cookies:
        return 'netflix'
    if 'oai-client-auth-info' in cookies:
        return 'chatgpt'
    if 'sessionKey' in cookies and 'routingHint' in cookies:
        return 'claude'
    if 'sessionid' in cookies or 'sid_tt' in cookies:
        return 'tiktok'
    if 'sso' in cookies and 'sso-rw' in cookies:
        return 'grok'
    return 'unknown'


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


def parse_json_cookies(content: str) -> Dict[str, str]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if k and v}
    except:
        pass
    return {}


def parse_key_value_cookies(content: str) -> Dict[str, str]:
    cookies = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def parse_cookies(content: str) -> Dict[str, str]:
    cookies = {}
    
    if content.strip().startswith('{'):
        cookies = parse_json_cookies(content)
        if cookies:
            return cookies
    
    if '\t' in content:
        cookies = parse_netscape_cookies(content)
        if cookies:
            return cookies
    
    if '=' in content:
        cookies = parse_key_value_cookies(content)
        if cookies:
            return cookies
    
    return cookies


@app.route('/check', methods=['POST'])
def check_cookies():
    try:
        content = request.data.decode('utf-8')
        
        if not content or not content.strip():
            return jsonify({'success': False, 'error': 'Empty request body'}), 400
        
        cookies = parse_cookies(content)
        
        if not cookies:
            return jsonify({'success': False, 'error': 'No valid cookies found'}), 400
        
        platform = detect_platform(cookies)
        
        checkers = {
            'grok': GrokChecker(),
            'chatgpt': ChatGPTChecker(),
            'claude': ClaudeChecker(),
            'tiktok': TikTokChecker(),
            'netflix': NetflixChecker()
        }
        
        if platform in checkers:
            valid, result = checkers[platform].check(cookies)
            return jsonify({
                'success': True,
                'platform': platform,
                'valid': valid,
                'result': result,
                'cookies_found': len(cookies)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unknown platform',
                'supported': list(checkers.keys()),
                'cookies_found': len(cookies)
            }), 400
        
    except UnicodeDecodeError:
        return jsonify({'success': False, 'error': 'Invalid encoding'}), 400
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/check/<platform>', methods=['POST'])
def check_platform(platform: str):
    try:
        content = request.data.decode('utf-8')
        
        if not content or not content.strip():
            return jsonify({'success': False, 'error': 'Empty request body'}), 400
        
        cookies = parse_cookies(content)
        
        if not cookies:
            return jsonify({'success': False, 'error': 'No valid cookies found'}), 400
        
        checkers = {
            'grok': GrokChecker(),
            'chatgpt': ChatGPTChecker(),
            'claude': ClaudeChecker(),
            'tiktok': TikTokChecker(),
            'netflix': NetflixChecker()
        }
        
        if platform not in checkers:
            return jsonify({
                'success': False,
                'error': f'Platform "{platform}" not supported',
                'supported': list(checkers.keys())
            }), 400
        
        valid, result = checkers[platform].check(cookies)
        return jsonify({
            'success': True,
            'platform': platform,
            'valid': valid,
            'result': result,
            'cookies_found': len(cookies)
        })
        
    except UnicodeDecodeError:
        return jsonify({'success': False, 'error': 'Invalid encoding'}), 400
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/detect', methods=['POST'])
def detect():
    try:
        content = request.data.decode('utf-8')
        cookies = parse_cookies(content)
        
        if not cookies:
            return jsonify({'success': False, 'error': 'No cookies found'}), 400
        
        platform = detect_platform(cookies)
        
        checkers = {
            'grok': GrokChecker(),
            'chatgpt': ChatGPTChecker(),
            'claude': ClaudeChecker(),
            'tiktok': TikTokChecker(),
            'netflix': NetflixChecker()
        }
        
        required_cookies = []
        if platform in checkers:
            required_cookies = checkers[platform].required_cookies
        
        return jsonify({
            'success': True,
            'platform': platform,
            'required_cookies': required_cookies,
            'cookies_found': list(cookies.keys())
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/platforms', methods=['GET'])
def platforms():
    return jsonify({
        'success': True,
        'platforms': {
            'grok': {
                'name': 'Grok',
                'required_cookies': ['sso', 'sso-rw']
            },
            'chatgpt': {
                'name': 'ChatGPT',
                'required_cookies': ['oai-client-auth-info']
            },
            'claude': {
                'name': 'Claude AI',
                'required_cookies': ['sessionKey', 'routingHint']
            },
            'tiktok': {
                'name': 'TikTok',
                'required_cookies': ['sessionid', 'sid_tt']
            },
            'netflix': {
                'name': 'Netflix',
                'required_cookies': ['NetflixId', 'SecureNetflixId']
            }
        }
    })


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'name': 'Multi-Platform Cookie Checker API',
        'version': '1.0.0',
        'status': 'running',
        'platforms': ['grok', 'chatgpt', 'claude', 'tiktok', 'netflix'],
        'endpoints': {
            '/': 'GET - API information',
            '/check': 'POST - Check cookies (auto-detect platform)',
            '/check/<platform>': 'POST - Check cookies for specific platform',
            '/detect': 'POST - Detect platform from cookies',
            '/platforms': 'GET - List supported platforms'
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=False)
