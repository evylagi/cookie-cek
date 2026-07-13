from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import os
import configparser
from datetime import datetime

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('PORT', 10000))

def parse_cookies(cookie_text):
    cookies = {}
    for line in cookie_text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            cookies[parts[5].strip()] = parts[6].strip()
    return cookies

def safe_get(data, key, default='N/A'):
    if data is None or not isinstance(data, dict):
        return default
    value = data.get(key)
    return value if value is not None else default

def check_chatgpt(cookie_text):
    try:
        cookies = parse_cookies(cookie_text)
        if not cookies:
            return {"success": False, "error": "No valid cookies found"}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/150.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        }
        response = requests.get('https://chatgpt.com', cookies=cookies, headers=headers, timeout=10)
        
        if response.status_code == 200:
            match = re.search(r'<script[^>]*id="client-bootstrap"[^>]*>(.*?)</script>', response.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                session = data.get('session', {})
                account = session.get('account', {})
                user = session.get('user', {})
                
                return {
                    "success": True,
                    "service": "chatgpt",
                    "details": {
                        "user_name": safe_get(user, 'name'),
                        "user_email": safe_get(user, 'email'),
                        "user_id": safe_get(user, 'id'),
                        "account_id": safe_get(account, 'id'),
                        "plan_type": safe_get(account, 'planType', 'FREE'),
                        "structure": safe_get(account, 'structure'),
                        "region": safe_get(account, 'residencyRegion'),
                        "fedramp": str(safe_get(account, 'isFedrampCompliantWorkspace', 'False')),
                        "delinquent": str(safe_get(account, 'isDelinquent', 'False')),
                        "expires": safe_get(session, 'expires'),
                        "status": safe_get(data, 'authStatus')
                    }
                }
        
        return {"success": False, "error": "Session invalid or expired"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_claude(cookie_text):
    try:
        cookies = parse_cookies(cookie_text)
        if not cookies:
            return {"success": False, "error": "No valid cookies found"}
        
        org = cookies.get('lastActiveOrg')
        if not org:
            return {"success": False, "error": "No organization found"}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
            'anthropic-client-platform': 'web_claude_ai',
        }
        
        response = requests.get(
            f'https://claude.ai/edge-api/bootstrap/{org}/app_start',
            cookies=cookies,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            account = data.get('account', {})
            memberships = account.get('memberships', [])
            org_data = memberships[0].get('organization', {}) if memberships else {}
            
            return {
                "success": True,
                "service": "claude",
                "details": {
                    "user_name": safe_get(account, 'display_name'),
                    "user_email": safe_get(account, 'email_address'),
                    "user_id": safe_get(account, 'uuid'),
                    "account_id": safe_get(account, 'id'),
                    "plan_type": safe_get(org_data, 'rate_limit_tier', 'free'),
                    "organization": safe_get(org_data, 'name'),
                    "org_id": safe_get(org_data, 'uuid'),
                    "role": safe_get(memberships[0], 'role') if memberships else 'N/A',
                    "seat_tier": safe_get(memberships[0], 'seat_tier') if memberships else 'N/A',
                    "billing": safe_get(org_data, 'billing_type'),
                    "verified": str(safe_get(account, 'is_verified', 'False')),
                    "created": safe_get(account, 'created_at')
                }
            }
        return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_grok(cookie_text):
    try:
        cookies = parse_cookies(cookie_text)
        if not cookies:
            return {"success": False, "error": "No valid cookies found"}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(
            'https://grok.com/api/auth/session',
            cookies=cookies,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'authenticated':
                s = data.get('session', {})
                tier = str(s.get('sessionTierId', '2'))
                plan_map = {'2': 'Free', '3': 'SuperGrok', '4': 'SuperGrok Pro'}
                
                return {
                    "success": True,
                    "service": "grok",
                    "details": {
                        "user_name": f"{s.get('givenName', '')} {s.get('familyName', '')}".strip() or 'N/A',
                        "user_email": safe_get(s, 'email'),
                        "user_id": safe_get(s, 'userId'),
                        "plan_type": plan_map.get(tier, 'Free'),
                        "tier_id": tier,
                        "org_id": safe_get(s, 'organizationId'),
                        "org_type": safe_get(s, 'organizationType'),
                        "x_user_id": safe_get(s, 'xUserId'),
                        "x_username": safe_get(s, 'xUsername'),
                        "x_premium": str(bool(s.get('xSubscriptionType'))),
                        "x_sub_type": safe_get(s, 'xSubscriptionType'),
                        "tos": safe_get(s, 'tosAcceptedVersion'),
                        "session_id": safe_get(s, 'sessionId'),
                        "email_domain": safe_get(s, 'emailDomain'),
                        "created": safe_get(s, 'createTime')
                    }
                }
            return {"success": False, "error": "Not authenticated"}
        return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_netflix(cookie_text):
    try:
        cookies = parse_cookies(cookie_text)
        if not cookies:
            return {"success": False, "error": "No valid cookies found"}
        
        session = requests.Session()
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.netflix.com', path='/')
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
        }
        
        response = session.get('https://www.netflix.com/YourAccount', timeout=15)
        
        if response.status_code == 200:
            html = response.text
            
            return {
                "success": True,
                "service": "netflix",
                "details": {
                    "user_name": re.search(r'"firstName":"([^"]+)"', html).group(1) if re.search(r'"firstName":"([^"]+)"', html) else 'N/A',
                    "user_email": re.search(r'"email":"([^"]+)"', html).group(1) if re.search(r'"email":"([^"]+)"', html) else 'N/A',
                    "user_id": cookies.get('NetflixId', 'N/A')[:20] + '...',
                    "plan_type": re.search(r'"planName":"([^"]+)"', html).group(1) if re.search(r'"planName":"([^"]+)"', html) else 'Unknown',
                    "member_since": re.search(r'"memberSince":"([^"]+)"', html).group(1) if re.search(r'"memberSince":"([^"]+)"', html) else 'N/A',
                    "country": re.search(r'"currentCountry":"([^"]+)"', html).group(1) if re.search(r'"currentCountry":"([^"]+)"', html) else 'N/A',
                    "status": re.search(r'"membershipStatus":"([^"]+)"', html).group(1) if re.search(r'"membershipStatus":"([^"]+)"', html) else 'N/A',
                    "next_billing": re.search(r'"nextBillingDate"[^}]*"value":"([^"]+)"', html).group(1) if re.search(r'"nextBillingDate"[^}]*"value":"([^"]+)"', html) else 'N/A',
                    "payment": re.search(r'"paymentMethod"[^}]*"value":"([^"]+)"', html).group(1) if re.search(r'"paymentMethod"[^}]*"value":"([^"]+)"', html) else 'N/A',
                    "premium": 'Yes' if 'Premium' in html else 'No'
                }
            }
        return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_tiktok(cookie_text):
    try:
        cookies = parse_cookies(cookie_text)
        if not cookies:
            return {"success": False, "error": "No valid cookies found"}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(
            'https://www.tiktok.com/passport/web/account/info/',
            params={'aid': '1459', 'user_is_login': 'true'},
            cookies=cookies,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('message') == 'success':
                account = data.get('data', {})
                
                # Get stats
                stats_response = requests.get(
                    'https://www.tiktok.com/api/user/detail/self/',
                    params={'aid': '1988', 'user_is_login': 'true'},
                    cookies=cookies,
                    headers=headers,
                    timeout=10
                )
                
                stats = {}
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    if stats_data.get('statusCode') == 0:
                        stats = stats_data.get('userInfo', {}).get('stats', {})
                
                return {
                    "success": True,
                    "service": "tiktok",
                    "details": {
                        "user_name": safe_get(account, 'screen_name'),
                        "user_email": safe_get(account, 'email'),
                        "user_id": safe_get(account, 'user_id_str'),
                        "username": safe_get(account, 'unique_id'),
                        "verified": str(account.get('verified', False)),
                        "private": str(account.get('privacy', {}).get('is_private', False)),
                        "followers": stats.get('followerCount', 0),
                        "following": stats.get('followingCount', 0),
                        "videos": stats.get('videoCount', 0),
                        "likes": stats.get('diggCount', 0),
                        "plan_type": 'verified' if account.get('verified') else 'normal'
                    }
                }
            return {"success": False, "error": data.get('message', 'Unknown error')}
        return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def detect_service(cookies):
    if any(c in cookies for c in ['oai-did', '__Secure-next-auth.session-token.0']):
        return 'chatgpt'
    if 'sessionKey' in cookies and 'routingHint' in cookies:
        return 'claude'
    if 'sessionid' in cookies and 'sid_tt' in cookies:
        return 'tiktok'
    if 'NetflixId' in cookies and 'SecureNetflixId' in cookies:
        return 'netflix'
    if 'sso' in cookies:
        return 'grok'
    return 'chatgpt'

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'Cookie Checker API',
        'version': '2.0',
        'status': 'online',
        'services': ['chatgpt', 'claude', 'grok', 'netflix', 'tiktok'],
        'endpoints': ['/health', '/check', '/<service>/check']
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/check', methods=['POST'])
def auto_check():
    try:
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'success': False, 'error': 'Missing cookies field'}), 400
        
        cookies = parse_cookies(data['cookies'])
        if not cookies:
            return jsonify({'success': False, 'error': 'No valid cookies found'}), 400
        
        service = detect_service(cookies)
        
        if service == 'chatgpt':
            result = check_chatgpt(data['cookies'])
        elif service == 'claude':
            result = check_claude(data['cookies'])
        elif service == 'grok':
            result = check_grok(data['cookies'])
        elif service == 'netflix':
            result = check_netflix(data['cookies'])
        elif service == 'tiktok':
            result = check_tiktok(data['cookies'])
        else:
            result = check_chatgpt(data['cookies'])
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/<service>/check', methods=['POST'])
def service_check(service):
    try:
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'success': False, 'error': 'Missing cookies field'}), 400
        
        if service == 'chatgpt':
            result = check_chatgpt(data['cookies'])
        elif service == 'claude':
            result = check_claude(data['cookies'])
        elif service == 'grok':
            result = check_grok(data['cookies'])
        elif service == 'netflix':
            result = check_netflix(data['cookies'])
        elif service == 'tiktok':
            result = check_tiktok(data['cookies'])
        else:
            return jsonify({'success': False, 'error': f'Service {service} not found'}), 404
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
