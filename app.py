from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('PORT', 10000))

def parse_netscape_cookies(cookie_text):
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

def safe_get(data, key, default='N/A'):
    if not data:
        return default
    value = data.get(key)
    return value if value is not None else default

def check_chatgpt(cookie_text):
    try:
        cookies = parse_netscape_cookies(cookie_text)
        headers = {
            'host': 'chatgpt.com',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/150.0.0.0 Mobile Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
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
                        "residency_region": safe_get(account, 'residencyRegion'),
                        "is_fedramp": safe_get(account, 'isFedrampCompliantWorkspace', 'False'),
                        "is_delinquent": safe_get(account, 'isDelinquent', 'False'),
                        "session_expires": safe_get(session, 'expires'),
                        "auth_status": safe_get(data, 'authStatus')
                    }
                }
        return {"success": False, "service": "chatgpt", "error": "Session invalid or expired"}
    except Exception as e:
        return {"success": False, "service": "chatgpt", "error": str(e)}

def check_claude(cookie_text):
    try:
        cookies = parse_netscape_cookies(cookie_text)
        headers = {
            'host': 'claude.ai',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'accept': 'application/json',
            'anthropic-client-platform': 'web_claude_ai',
        }
        org_uuid = cookies.get('lastActiveOrg', '')
        if not org_uuid:
            return {"success": False, "service": "claude", "error": "No organization UUID found"}
        
        response = requests.get(
            f'https://claude.ai/edge-api/bootstrap/{org_uuid}/app_start',
            cookies=cookies,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            account = data.get('account', {})
            memberships = account.get('memberships', [])
            org_data = {}
            if memberships:
                org_data = memberships[0].get('organization', {})
            
            plan_type = "free"
            if org_data.get('rate_limit_tier'):
                plan_type = org_data.get('rate_limit_tier')
            
            return {
                "success": True,
                "service": "claude",
                "details": {
                    "user_name": safe_get(account, 'display_name'),
                    "user_email": safe_get(account, 'email_address'),
                    "user_id": safe_get(account, 'uuid'),
                    "account_id": safe_get(account, 'id'),
                    "plan_type": plan_type,
                    "organization": safe_get(org_data, 'name'),
                    "org_id": safe_get(org_data, 'uuid'),
                    "role": safe_get(memberships[0], 'role') if memberships else 'N/A',
                    "seat_tier": safe_get(memberships[0], 'seat_tier') if memberships else 'N/A',
                    "billing_type": safe_get(org_data, 'billing_type'),
                    "verified": str(safe_get(account, 'is_verified', 'False')),
                    "created_at": safe_get(account, 'created_at')
                }
            }
        return {"success": False, "service": "claude", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "service": "claude", "error": str(e)}

def check_grok(cookie_text):
    try:
        cookies = parse_netscape_cookies(cookie_text)
        headers = {
            'host': 'grok.com',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'accept': 'application/json',
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
                session = data.get('session', {})
                tier_id = str(session.get('sessionTierId', '2'))
                plan_map = {'2': 'Free', '3': 'SuperGrok', '4': 'SuperGrok Pro'}
                
                return {
                    "success": True,
                    "service": "grok",
                    "details": {
                        "user_name": f"{session.get('givenName', '')} {session.get('familyName', '')}".strip() or 'N/A',
                        "user_email": safe_get(session, 'email'),
                        "user_id": safe_get(session, 'userId'),
                        "plan_type": plan_map.get(tier_id, 'Free'),
                        "tier_id": tier_id,
                        "organization_id": safe_get(session, 'organizationId'),
                        "organization_type": safe_get(session, 'organizationType'),
                        "x_user_id": safe_get(session, 'xUserId'),
                        "x_username": safe_get(session, 'xUsername'),
                        "has_x_premium": str(bool(session.get('xSubscriptionType'))),
                        "x_subscription_type": safe_get(session, 'xSubscriptionType'),
                        "tos_accepted": safe_get(session, 'tosAcceptedVersion'),
                        "session_id": safe_get(session, 'sessionId'),
                        "email_domain": safe_get(session, 'emailDomain'),
                        "create_time": safe_get(session, 'createTime')
                    }
                }
            return {"success": False, "service": "grok", "error": "Not authenticated"}
        return {"success": False, "service": "grok", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "service": "grok", "error": str(e)}

def check_netflix(cookie_text):
    try:
        cookies = parse_netscape_cookies(cookie_text)
        session = requests.Session()
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.netflix.com', path='/')
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
        }
        session.headers.update(headers)
        
        response = session.get('https://www.netflix.com/YourAccount', timeout=15)
        
        if response.status_code == 200:
            html = response.text
            
            email_match = re.search(r'"email":"([^"]+)"', html)
            name_match = re.search(r'"firstName":"([^"]+)"', html)
            plan_match = re.search(r'"planName":"([^"]+)"', html)
            member_since = re.search(r'"memberSince":"([^"]+)"', html)
            country_match = re.search(r'"currentCountry":"([^"]+)"', html)
            status_match = re.search(r'"membershipStatus":"([^"]+)"', html)
            next_billing = re.search(r'"nextBillingDate"[^}]*"value":"([^"]+)"', html)
            payment_method = re.search(r'"paymentMethod"[^}]*"value":"([^"]+)"', html)
            video_quality = re.search(r'"videoQuality"[^}]*"value":"([^"]+)"', html)
            max_streams = re.search(r'"maxStreams"[^}]*"value":([0-9]+)', html)
            
            netflix_id = cookies.get('NetflixId', 'N/A')
            if netflix_id != 'N/A':
                netflix_id = netflix_id[:20] + '...'
            
            return {
                "success": True,
                "service": "netflix",
                "details": {
                    "user_name": name_match.group(1) if name_match else 'N/A',
                    "user_email": email_match.group(1) if email_match else 'N/A',
                    "user_id": netflix_id,
                    "plan_type": plan_match.group(1) if plan_match else 'Unknown',
                    "member_since": member_since.group(1) if member_since else 'N/A',
                    "country": country_match.group(1) if country_match else 'N/A',
                    "status": status_match.group(1) if status_match else 'N/A',
                    "next_billing": next_billing.group(1) if next_billing else 'N/A',
                    "payment_method": payment_method.group(1) if payment_method else 'N/A',
                    "video_quality": video_quality.group(1) if video_quality else 'N/A',
                    "max_streams": max_streams.group(1) if max_streams else 'N/A',
                    "is_premium": "Yes" if "Premium" in (plan_match.group(1) if plan_match else '') else "No"
                }
            }
        return {"success": False, "service": "netflix", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "service": "netflix", "error": str(e)}

def check_tiktok(cookie_text):
    try:
        cookies = parse_netscape_cookies(cookie_text)
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
                        user_info = stats_data.get('userInfo', {})
                        stats = user_info.get('stats', {})
                
                return {
                    "success": True,
                    "service": "tiktok",
                    "details": {
                        "user_name": safe_get(account, 'screen_name'),
                        "user_email": safe_get(account, 'email'),
                        "user_id": safe_get(account, 'user_id_str'),
                        "unique_id": safe_get(account, 'unique_id'),
                        "verified": str(account.get('verified', False)),
                        "private": str(account.get('privacy', {}).get('is_private', False)),
                        "followers": stats.get('followerCount', 0),
                        "following": stats.get('followingCount', 0),
                        "videos": stats.get('videoCount', 0),
                        "likes": stats.get('diggCount', 0),
                        "plan_type": "verified" if account.get('verified', False) else "normal"
                    }
                }
            return {"success": False, "service": "tiktok", "error": data.get('message', 'Unknown error')}
        return {"success": False, "service": "tiktok", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "service": "tiktok", "error": str(e)}

# ============================================
# ROUTES
# ============================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'Universal Cookie Checker API',
        'version': '2.0.0',
        'status': 'online',
        'endpoints': {
            '/': 'GET - This page',
            '/health': 'GET - Health check',
            '/check': 'POST - Auto-detect service',
            '/chatgpt/check': 'POST - Check ChatGPT cookies',
            '/claude/check': 'POST - Check Claude cookies',
            '/grok/check': 'POST - Check Grok cookies',
            '/netflix/check': 'POST - Check Netflix cookies',
            '/tiktok/check': 'POST - Check TikTok cookies'
        },
        'supported_services': ['chatgpt', 'claude', 'grok', 'netflix', 'tiktok']
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Universal Cookie Checker API',
        'version': '2.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/check', methods=['POST'])
def check_auto():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        cookie_text = data.get('cookies')
        if not cookie_text:
            return jsonify({'success': False, 'error': 'Missing "cookies" field'}), 400
        
        cookies = parse_netscape_cookies(cookie_text)
        if not cookies:
            return jsonify({'success': False, 'error': 'No valid cookies found'}), 400
        
        if 'sessionKey' in cookies and 'routingHint' in cookies:
            result = check_claude(cookie_text)
        elif 'sessionid' in cookies and 'sid_tt' in cookies:
            result = check_tiktok(cookie_text)
        elif 'NetflixId' in cookies and 'SecureNetflixId' in cookies:
            result = check_netflix(cookie_text)
        elif 'sso' in cookies:
            result = check_grok(cookie_text)
        else:
            result = check_chatgpt(cookie_text)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/chatgpt/check', methods=['POST'])
def chatgpt_check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        cookie_text = data.get('cookies')
        if not cookie_text:
            return jsonify({'success': False, 'error': 'Missing "cookies" field'}), 400
        result = check_chatgpt(cookie_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/claude/check', methods=['POST'])
def claude_check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        cookie_text = data.get('cookies')
        if not cookie_text:
            return jsonify({'success': False, 'error': 'Missing "cookies" field'}), 400
        result = check_claude(cookie_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/grok/check', methods=['POST'])
def grok_check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        cookie_text = data.get('cookies')
        if not cookie_text:
            return jsonify({'success': False, 'error': 'Missing "cookies" field'}), 400
        result = check_grok(cookie_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/netflix/check', methods=['POST'])
def netflix_check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        cookie_text = data.get('cookies')
        if not cookie_text:
            return jsonify({'success': False, 'error': 'Missing "cookies" field'}), 400
        result = check_netflix(cookie_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/tiktok/check', methods=['POST'])
def tiktok_check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        cookie_text = data.get('cookies')
        if not cookie_text:
            return jsonify({'success': False, 'error': 'Missing "cookies" field'}), 400
        result = check_tiktok(cookie_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'available_endpoints': [
            'GET /',
            'GET /health',
            'POST /check',
            'POST /chatgpt/check',
            'POST /claude/check',
            'POST /grok/check',
            'POST /netflix/check',
            'POST /tiktok/check'
        ]
    }), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
