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

def get_value(data, key, default='N/A'):
    if not data or not isinstance(data, dict):
        return default
    if '.' in key:
        for k in key.split('.'):
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return default
        return data if data is not None else default
    return data.get(key, default)

def detect_service(cookies, services):
    for name, cfg in services.items():
        for c in cfg.get('DETECTION', 'cookies', fallback='').split(','):
            if c.strip() in cookies:
                return name
    return 'chatgpt'

def load_services():
    services = {}
    for file in ['chatgpt.ini', 'claude.ini', 'grok.ini', 'netflix.ini', 'tiktok.ini']:
        if os.path.exists(file):
            cfg = configparser.ConfigParser()
            cfg.read(file)
            services[cfg.get('SERVICE', 'name').lower()] = cfg
    return services

def check_service(cookie_text, service, cfg):
    try:
        cookies = parse_cookies(cookie_text)
        if not cookies:
            return {"success": False, "error": "No valid cookies found"}

        url = f"https://{cfg.get('SERVICE', 'domain')}{cfg.get('SERVICE', 'endpoint')}"
        headers = dict(cfg.items('HEADERS'))
        
        if '{org}' in url:
            org = cookies.get('lastActiveOrg')
            if not org:
                return {"success": False, "error": "No organization found"}
            url = url.replace('{org}', org)

        resp = requests.get(url, cookies=cookies, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}"}

        data = resp.json() if 'json' in resp.headers.get('content-type', '') else resp.text
        details = {}
        plan_map = dict(cfg.items('PLAN_MAP')) if cfg.has_section('PLAN_MAP') else {}

        if service == 'chatgpt':
            match = re.search(r'<script[^>]*id="client-bootstrap"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                session = data.get('session', {})
                account = session.get('account', {})
                user = session.get('user', {})
                details = {
                    'user_name': user.get('name', 'N/A'),
                    'user_email': user.get('email', 'N/A'),
                    'user_id': user.get('id', 'N/A'),
                    'account_id': account.get('id', 'N/A'),
                    'plan_type': plan_map.get(account.get('planType', 'free'), 'FREE'),
                    'structure': account.get('structure', 'N/A'),
                    'region': account.get('residencyRegion', 'N/A'),
                    'fedramp': str(account.get('isFedrampCompliantWorkspace', False)),
                    'delinquent': str(account.get('isDelinquent', False)),
                    'expires': session.get('expires', 'N/A'),
                    'status': data.get('authStatus', 'N/A')
                }

        elif service == 'claude':
            account = data.get('account', {})
            memberships = account.get('memberships', [])
            org = memberships[0].get('organization', {}) if memberships else {}
            details = {
                'user_name': account.get('display_name', 'N/A'),
                'user_email': account.get('email_address', 'N/A'),
                'user_id': account.get('uuid', 'N/A'),
                'account_id': account.get('id', 'N/A'),
                'plan_type': plan_map.get(org.get('rate_limit_tier', 'free'), 'FREE'),
                'organization': org.get('name', 'N/A'),
                'org_id': org.get('uuid', 'N/A'),
                'role': memberships[0].get('role', 'N/A') if memberships else 'N/A',
                'seat_tier': memberships[0].get('seat_tier', 'N/A') if memberships else 'N/A',
                'billing': org.get('billing_type', 'N/A'),
                'verified': str(account.get('is_verified', False)),
                'created': account.get('created_at', 'N/A')
            }

        elif service == 'grok':
            if data.get('status') == 'authenticated':
                s = data.get('session', {})
                tier = str(s.get('sessionTierId', '2'))
                details = {
                    'user_name': f"{s.get('givenName', '')} {s.get('familyName', '')}".strip() or 'N/A',
                    'user_email': s.get('email', 'N/A'),
                    'user_id': s.get('userId', 'N/A'),
                    'plan_type': plan_map.get(tier, 'Free'),
                    'tier_id': tier,
                    'org_id': s.get('organizationId', 'N/A'),
                    'org_type': s.get('organizationType', 'N/A'),
                    'x_user_id': s.get('xUserId', 'N/A'),
                    'x_username': s.get('xUsername', 'N/A'),
                    'x_premium': str(bool(s.get('xSubscriptionType'))),
                    'x_sub_type': s.get('xSubscriptionType', 'N/A'),
                    'tos': s.get('tosAcceptedVersion', 'N/A'),
                    'session_id': s.get('sessionId', 'N/A'),
                    'email_domain': s.get('emailDomain', 'N/A'),
                    'created': s.get('createTime', 'N/A')
                }
            else:
                return {"success": False, "error": "Not authenticated"}

        elif service == 'netflix':
            html = resp.text
            details = {
                'user_name': re.search(r'"firstName":"([^"]+)"', html).group(1) if re.search(r'"firstName":"([^"]+)"', html) else 'N/A',
                'user_email': re.search(r'"email":"([^"]+)"', html).group(1) if re.search(r'"email":"([^"]+)"', html) else 'N/A',
                'user_id': cookies.get('NetflixId', 'N/A')[:20] + '...',
                'plan_type': re.search(r'"planName":"([^"]+)"', html).group(1) if re.search(r'"planName":"([^"]+)"', html) else 'Unknown',
                'member_since': re.search(r'"memberSince":"([^"]+)"', html).group(1) if re.search(r'"memberSince":"([^"]+)"', html) else 'N/A',
                'country': re.search(r'"currentCountry":"([^"]+)"', html).group(1) if re.search(r'"currentCountry":"([^"]+)"', html) else 'N/A',
                'status': re.search(r'"membershipStatus":"([^"]+)"', html).group(1) if re.search(r'"membershipStatus":"([^"]+)"', html) else 'N/A',
                'next_billing': re.search(r'"nextBillingDate"[^}]*"value":"([^"]+)"', html).group(1) if re.search(r'"nextBillingDate"[^}]*"value":"([^"]+)"', html) else 'N/A',
                'payment': re.search(r'"paymentMethod"[^}]*"value":"([^"]+)"', html).group(1) if re.search(r'"paymentMethod"[^}]*"value":"([^"]+)"', html) else 'N/A',
                'premium': 'Yes' if 'Premium' in html else 'No'
            }

        elif service == 'tiktok':
            if data.get('message') == 'success':
                account = data.get('data', {})
                r2 = requests.get('https://www.tiktok.com/api/user/detail/self/', 
                                 params={'aid': '1988'}, cookies=cookies, timeout=10)
                stats = r2.json().get('userInfo', {}).get('stats', {}) if r2.status_code == 200 else {}
                details = {
                    'user_name': account.get('screen_name', 'N/A'),
                    'user_email': account.get('email', 'N/A'),
                    'user_id': account.get('user_id_str', 'N/A'),
                    'username': account.get('unique_id', 'N/A'),
                    'verified': str(account.get('verified', False)),
                    'private': str(account.get('privacy', {}).get('is_private', False)),
                    'followers': stats.get('followerCount', 0),
                    'following': stats.get('followingCount', 0),
                    'videos': stats.get('videoCount', 0),
                    'likes': stats.get('diggCount', 0),
                    'plan_type': 'verified' if account.get('verified') else 'normal'
                }

        details['service'] = service
        return {"success": True, "details": details}

    except Exception as e:
        return {"success": False, "error": str(e)}

services = load_services()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'Cookie Checker API',
        'version': '2.0',
        'services': list(services.keys()),
        'endpoints': ['/health', '/check', '/<service>/check']
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'time': datetime.utcnow().isoformat()})

@app.route('/check', methods=['POST'])
def auto_check():
    try:
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'success': False, 'error': 'Missing cookies'}), 400
        
        cookies = parse_cookies(data['cookies'])
        if not cookies:
            return jsonify({'success': False, 'error': 'No valid cookies'}), 400
        
        service = detect_service(cookies, services)
        result = check_service(data['cookies'], service, services[service])
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/<service>/check', methods=['POST'])
def service_check(service):
    try:
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'success': False, 'error': 'Missing cookies'}), 400
        
        if service not in services:
            return jsonify({'success': False, 'error': f'Service {service} not found'}), 404
        
        result = check_service(data['cookies'], service, services[service])
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)