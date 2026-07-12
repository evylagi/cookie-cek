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

REQUEST_TIMEOUT = 15
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
            'priority': 'u=1, i',
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
            'platform': 'grok',
            'valid': False,
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
            headers = self.get_headers()
            
            response = requests.get(
                f'{self.base_url}/api/auth/session',
                cookies=cookies,
                headers=headers,
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
                    
                    sso_cookie = cookies.get('sso', '')
                    session_data = self.decode_sso_token(sso_cookie)
                    
                    result['session'] = {
                        'session_id': session_data.get('session_id', 'Unknown'),
                        'is_authenticated': True,
                    }
                    
                    result['settings'] = {
                        'device_id': cookies.get('grok_device_id', 'Unknown'),
                        'language': cookies.get('i18nextLng', 'en'),
                        'has_twitter_link': bool(cookies.get('_twpid')),
                    }
                    
                    if cookies.get('x-userid'):
                        result['user']['x_userid'] = cookies.get('x-userid')
                    
                    result['valid'] = True
                    return True, result
                else:
                    result['error'] = "Not authenticated - cookies may be expired"
                    return False, result
            elif response.status_code in [301, 302, 303, 307, 308]:
                result['error'] = "Redirected - cookies may be invalid or expired"
                result['redirect_location'] = response.headers.get('location', 'Unknown')
                return False, result
            elif response.status_code == 401:
                result['error'] = "Unauthorized - cookies are invalid or expired"
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


class ChatGPTChecker(BaseChecker):
    def __init__(self):
        super().__init__()
        self.name = "ChatGPT"
        self.required_cookies = ['oai-client-auth-info']
        self.session = requests.Session()
    
    def get_headers(self, accept: str = 'text/html') -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': accept,
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'DNT': '1'
        }
    
    def get_api_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Referer': 'https://chatgpt.com/',
            'DNT': '1'
        }
    
    def get_basic_info_from_cookies(self, cookies: Dict[str, str]) -> Dict[str, Any]:
        basic_info = {
            'user_name': None,
            'user_email': None,
            'user_picture': None,
            'user_id': None
        }
        
        if cookies and 'oai-client-auth-info' in cookies:
            try:
                import urllib.parse
                decoded = urllib.parse.unquote(cookies['oai-client-auth-info'])
                user_data = json.loads(decoded)
                user_info = user_data.get('user', {})
                basic_info['user_name'] = user_info.get('name')
                basic_info['user_email'] = user_info.get('email')
                basic_info['user_picture'] = user_info.get('picture')
                basic_info['user_id'] = user_info.get('id')
            except:
                pass
        
        return basic_info
    
    def extract_account_details(self, html_content: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        details = {
            'user_id': None,
            'user_name': None,
            'user_email': None,
            'user_image': None,
            'user_picture': None,
            'user_idp': None,
            'user_iat': None,
            'user_mfa': None,
            'account_id': None,
            'plan_type': None,
            'structure': None,
            'is_usage_based_seat': None,
            'is_conversation_classifier_enabled': None,
            'is_fedramp_compliant': None,
            'is_delinquent': None,
            'residency_region': None,
            'compute_residency': None,
            'session_expires': None,
            'access_token': None,
            'auth_provider': None,
            'session_token': None,
            'session_id': None,
            'cluster': None,
            'locale': None,
            'sec_fetch_site': None,
            'auth_status': None,
            'country': None,
            'region': None,
            'ip': None,
            'statsig_payload': None
        }
        
        basic = self.get_basic_info_from_cookies(cookies)
        details.update(basic)
        
        if not html_content:
            return details
        
        patterns = [
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'<script[^>]*id="client-bootstrap"[^>]*>(.*?)</script>',
            r'window\.__NEXT_DATA__\s*=\s*({.*?});',
            r'window\.__BOOTSTRAP_DATA__\s*=\s*({.*?});'
        ]
        
        bootstrap_data = None
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                try:
                    bootstrap_data = json.loads(match.group(1))
                    break
                except:
                    continue
        
        if not bootstrap_data:
            try:
                script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL)
                for script in script_matches:
                    if 'session' in script and ('user' in script or 'account' in script):
                        json_matches = re.findall(r'({[^{}]*"session"[^{}]*})', script)
                        for json_str in json_matches:
                            try:
                                data = json.loads(json_str)
                                if 'session' in data:
                                    bootstrap_data = data
                                    break
                            except:
                                continue
                        if bootstrap_data:
                            break
            except:
                pass
        
        if not bootstrap_data:
            return details
        
        try:
            session = bootstrap_data.get('session', {})
            account = session.get('account', {})
            user = session.get('user', {})
            
            details.update({
                'user_id': user.get('id') or details.get('user_id'),
                'user_name': user.get('name') or details.get('user_name'),
                'user_email': user.get('email') or details.get('user_email'),
                'user_image': user.get('image'),
                'user_picture': user.get('picture') or details.get('user_picture'),
                'user_idp': user.get('idp'),
                'user_iat': user.get('iat'),
                'user_mfa': user.get('mfa')
            })
            
            details.update({
                'account_id': account.get('id'),
                'plan_type': account.get('planType'),
                'structure': account.get('structure'),
                'is_usage_based_seat': account.get('isUsageBasedSeatEnabled'),
                'is_conversation_classifier_enabled': account.get('isConversationClassifierEnabledForWorkspace'),
                'is_fedramp_compliant': account.get('isFedrampCompliantWorkspace'),
                'is_delinquent': account.get('isDelinquent'),
                'residency_region': account.get('residencyRegion'),
                'compute_residency': account.get('computeResidency')
            })
            
            access_token = session.get('accessToken')
            session_token = session.get('sessionToken')
            details.update({
                'session_expires': session.get('expires'),
                'access_token': access_token[:150] + '...' if access_token and len(access_token) > 150 else access_token,
                'auth_provider': session.get('authProvider'),
                'session_token': session_token[:100] + '...' if session_token and len(session_token) > 100 else session_token,
                'session_id': bootstrap_data.get('sessionId'),
                'cluster': session.get('cluster'),
                'locale': session.get('locale'),
                'sec_fetch_site': session.get('secFetchSite'),
                'auth_status': bootstrap_data.get('authStatus')
            })
            
            details['statsig_payload'] = bootstrap_data.get('statsigPayload')
            statsig = details['statsig_payload']
            
            if isinstance(statsig, dict):
                user_meta = statsig.get('user', {})
                details['country'] = user_meta.get('country')
                details['region'] = user_meta.get('region')
                details['ip'] = user_meta.get('ip')
            elif isinstance(statsig, str):
                try:
                    statsig_dict = json.loads(statsig)
                    user_meta = statsig_dict.get('user', {})
                    details['country'] = user_meta.get('country')
                    details['region'] = user_meta.get('region')
                    details['ip'] = user_meta.get('ip')
                except:
                    pass
                    
        except Exception as e:
            pass
        
        return details
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'platform': 'chatgpt',
            'valid': False,
            'user': {},
            'plan': {},
            'session': {},
            'settings': {},
            'location': {},
            'account': {},
            'error': None,
            'raw_details': {}
        }
        
        valid, missing = self.validate_required_cookies(cookies)
        if not valid:
            result['error'] = f"Missing cookies: {', '.join(missing)}"
            return False, result
        
        try:
            session = requests.Session()
            session.cookies.update(cookies)
            
            headers = self.get_headers()
            
            response = session.get(
                'https://chatgpt.com',
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            if response.status_code == 403:
                api_headers = self.get_api_headers()
                api_response = session.get(
                    'https://chatgpt.com/api/auth/session',
                    headers=api_headers,
                    timeout=REQUEST_TIMEOUT
                )
                
                if api_response.status_code == 200:
                    api_data = api_response.json()
                    if api_data.get('user'):
                        user = api_data.get('user', {})
                        details = {
                            'user_id': user.get('id'),
                            'user_name': user.get('name'),
                            'user_email': user.get('email'),
                            'user_picture': user.get('picture'),
                            'session_expires': api_data.get('expires'),
                            'access_token': api_data.get('accessToken', '')[:150] + '...' if api_data.get('accessToken') else None,
                        }
                        
                        try:
                            accounts_response = session.get(
                                'https://chatgpt.com/api/accounts',
                                headers=api_headers,
                                timeout=REQUEST_TIMEOUT
                            )
                            if accounts_response.status_code == 200:
                                accounts_data = accounts_response.json()
                                if accounts_data and len(accounts_data) > 0:
                                    account = accounts_data[0]
                                    details.update({
                                        'account_id': account.get('id'),
                                        'plan_type': account.get('planType'),
                                        'structure': account.get('structure'),
                                        'is_delinquent': account.get('isDelinquent')
                                    })
                        except:
                            pass
                        
                        result['user'] = {
                            'id': details.get('user_id', 'Unknown'),
                            'name': details.get('user_name', 'Unknown'),
                            'email': details.get('user_email', 'Unknown'),
                            'picture': details.get('user_picture'),
                        }
                        
                        result['plan'] = {
                            'type': details.get('plan_type', 'Unknown'),
                            'structure': details.get('structure', 'Unknown'),
                            'is_delinquent': details.get('is_delinquent', False)
                        }
                        
                        result['session'] = {
                            'expires': details.get('session_expires'),
                            'access_token': details.get('access_token')
                        }
                        
                        result['valid'] = True
                        return True, result
                
                basic = self.get_basic_info_from_cookies(cookies)
                if basic.get('user_name') or basic.get('user_email'):
                    result['user'] = {
                        'name': basic.get('user_name', 'Unknown'),
                        'email': basic.get('user_email', 'Unknown'),
                        'picture': basic.get('user_picture'),
                        'id': basic.get('user_id')
                    }
                    result['error'] = "Session may be expired, but cached user info available from cookie"
                    return False, result
                else:
                    result['error'] = f"HTTP {response.status_code} - Access denied"
                    return False, result
            
            if response.status_code == 200:
                details = self.extract_account_details(response.text, cookies)
                result['raw_details'] = details
                
                is_active = details.get('plan_type') is not None
                
                if not is_active:
                    api_headers = self.get_api_headers()
                    api_response = session.get(
                        'https://chatgpt.com/api/auth/session',
                        headers=api_headers,
                        timeout=REQUEST_TIMEOUT
                    )
                    if api_response.status_code == 200:
                        api_data = api_response.json()
                        if api_data.get('user'):
                            is_active = True
                            user = api_data.get('user', {})
                            details.update({
                                'user_id': user.get('id'),
                                'user_name': user.get('name'),
                                'user_email': user.get('email'),
                                'user_picture': user.get('picture'),
                                'session_expires': api_data.get('expires'),
                                'access_token': api_data.get('accessToken', '')[:150] + '...' if api_data.get('accessToken') else None,
                            })
                
                if is_active:
                    result['user'] = {
                        'id': details.get('user_id', 'Unknown'),
                        'name': details.get('user_name', 'Unknown'),
                        'email': details.get('user_email', 'Unknown'),
                        'picture': details.get('user_picture'),
                        'image': details.get('user_image'),
                        'idp': details.get('user_idp'),
                        'mfa_enabled': details.get('user_mfa', False),
                        'iat': details.get('user_iat')
                    }
                    
                    result['plan'] = {
                        'type': details.get('plan_type', 'Unknown'),
                        'structure': details.get('structure', 'Unknown'),
                        'is_usage_based_seat': details.get('is_usage_based_seat', False),
                        'is_conversation_classifier_enabled': details.get('is_conversation_classifier_enabled', False),
                        'is_fedramp_compliant': details.get('is_fedramp_compliant', False),
                        'is_delinquent': details.get('is_delinquent', False),
                        'residency_region': details.get('residency_region'),
                        'compute_residency': details.get('compute_residency')
                    }
                    
                    result['account'] = {
                        'id': details.get('account_id'),
                        'auth_status': details.get('auth_status')
                    }
                    
                    result['session'] = {
                        'expires': details.get('session_expires'),
                        'auth_provider': details.get('auth_provider'),
                        'session_id': details.get('session_id'),
                        'cluster': details.get('cluster'),
                        'sec_fetch_site': details.get('sec_fetch_site'),
                        'access_token': details.get('access_token'),
                        'session_token': details.get('session_token')
                    }
                    
                    result['settings'] = {
                        'locale': details.get('locale')
                    }
                    
                    result['location'] = {
                        'country': details.get('country'),
                        'region': details.get('region'),
                        'ip': details.get('ip')
                    }
                    
                    result['valid'] = True
                    return True, result
                else:
                    if details.get('user_name') or details.get('user_email'):
                        result['user'] = {
                            'name': details.get('user_name', 'Unknown'),
                            'email': details.get('user_email', 'Unknown'),
                            'picture': details.get('user_picture'),
                            'id': details.get('user_id')
                        }
                        result['error'] = "Session expired, but cached user info available"
                    else:
                        result['error'] = "Invalid session"
                    return False, result
            else:
                result['error'] = f"HTTP {response.status_code} - Could not access ChatGPT"
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
        self.required_cookies = ['sessionKey', 'routingHint', 'cf_clearance']
        self.base_url = "https://claude.ai"
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'platform': 'claude',
            'valid': False,
            'user': {},
            'org': {},
            'plan': {},
            'settings': {},
            'models': [],
            'features': [],
            'permissions': [],
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
                result['error'] = "No organization UUID found"
                return False, result
            
            response = requests.get(
                f'https://claude.ai/edge-api/bootstrap/{org_uuid}/app_start',
                cookies=cookies,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                account = data.get('account', {})
                
                result['user'] = {
                    'uuid': account.get('uuid'),
                    'name': account.get('display_name', 'Unknown'),
                    'full_name': account.get('full_name', 'Unknown'),
                    'email': account.get('email_address', 'Unknown'),
                    'verified': account.get('is_verified', False),
                    'age_verified': account.get('age_is_verified', False),
                    'anonymous': account.get('is_anonymous', False),
                    'created_at': account.get('created_at'),
                }
                
                memberships = account.get('memberships', [])
                if memberships:
                    membership = memberships[0]
                    org = membership.get('organization', {})
                    result['org'] = {
                        'uuid': org.get('uuid'),
                        'name': org.get('name', 'Unknown'),
                        'role': membership.get('role', 'Unknown'),
                        'seat_tier': membership.get('seat_tier'),
                        'rate_limit_tier': org.get('rate_limit_tier'),
                        'billing_type': org.get('billing_type'),
                        'free_credits_status': org.get('free_credits_status'),
                    }
                
                access = data.get('current_user_access', {})
                result['features'] = access.get('features', [])
                result['permissions'] = access.get('account_permissions', [])
                
                plan_response = requests.get(
                    f'https://claude.ai/api/organizations/{org_uuid}/paused_subscription_details',
                    cookies=cookies,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT
                )
                if plan_response.status_code == 200:
                    plan_data = plan_response.json()
                    result['plan'] = {
                        'type': plan_data.get('plan_type', 'free'),
                        'price': plan_data.get('price'),
                        'currency': plan_data.get('currency')
                    }
                
                result['valid'] = True
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
        self.required_cookies = ['sessionid', 'sid_tt', 'uid_tt']
    
    def check(self, cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        result = {
            'platform': 'tiktok',
            'valid': False,
            'user': {},
            'stats': {},
            'settings': {},
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
                data = response.json()
                
                if data.get('message') == 'success':
                    account = data.get('data', {})
                    result['user'] = {
                        'username': account.get('username', 'Unknown'),
                        'user_id': account.get('user_id_str', 'Unknown'),
                        'display_name': account.get('screen_name', 'Unknown'),
                        'email': account.get('email', 'Unknown'),
                        'verified': account.get('verified', False),
                        'private': account.get('private', False),
                        'profile_pic': account.get('profile_pic_url'),
                    }
                    
                    stats_response = requests.get(
                        'https://www.tiktok.com/api/user/detail/self/',
                        params={'aid': '1988', 'user_is_login': 'true'},
                        cookies=cookies,
                        headers=headers,
                        timeout=REQUEST_TIMEOUT
                    )
                    if stats_response.status_code == 200:
                        stats_data = stats_response.json()
                        if stats_data.get('statusCode') == 0:
                            user_info = stats_data.get('userInfo', {})
                            stats = user_info.get('stats', {})
                            user = user_info.get('user', {})
                            
                            result['stats'] = {
                                'followers': stats.get('followerCount', 0),
                                'following': stats.get('followingCount', 0),
                                'videos': stats.get('videoCount', 0),
                                'likes': stats.get('diggCount', 0),
                            }
                            
                            result['settings'] = {
                                'bio': user.get('signature', ''),
                                'region': user.get('region'),
                            }
                    
                    result['valid'] = True
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
            'platform': 'netflix',
            'valid': False,
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
                'Accept': 'application/json, text/plain, */*',
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
            
            email_patterns = [
                r'"email":"([^"]+)"',
                r'"userEmail":"([^"]+)"',
                r'"accountEmail":"([^"]+)"'
            ]
            for pattern in email_patterns:
                match = re.search(pattern, html)
                if match:
                    info['email'] = match.group(1)
                    break
            
            name_patterns = [
                r'"firstName":"([^"]+)"',
                r'"profileName":"([^"]+)"',
                r'"fullName":"([^"]+)"'
            ]
            for pattern in name_patterns:
                match = re.search(pattern, html)
                if match:
                    info['name'] = match.group(1)
                    break
            
            plan_patterns = [
                r'"planName":"([^"]+)"',
                r'"plan":"([^"]+)"'
            ]
            for pattern in plan_patterns:
                match = re.search(pattern, html)
                if match:
                    info['plan'] = match.group(1)
                    break
            
            since_match = re.search(r'"memberSince":"([^"]+)"', html)
            if since_match:
                info['member_since'] = since_match.group(1)
            
            country_match = re.search(r'"currentCountry":"([^"]+)"', html)
            if country_match:
                info['country'] = country_match.group(1)
            
            if info:
                result['user'] = {
                    'name': info.get('name', 'Unknown'),
                    'email': info.get('email', 'Unknown'),
                }
                result['plan'] = {
                    'type': info.get('plan', 'Unknown'),
                    'member_since': info.get('member_since'),
                }
                result['account'] = {
                    'country': info.get('country'),
                    'status': 'Active',
                }
                result['valid'] = True
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
    if 'sso' in cookies and 'sso-rw' in cookies:
        return 'grok'
    if 'oai-client-auth-info' in cookies:
        return 'chatgpt'
    if 'sessionKey' in cookies and 'routingHint' in cookies:
        return 'claude'
    if 'sessionid' in cookies or 'sid_tt' in cookies:
        return 'tiktok'
    if 'NetflixId' in cookies and 'SecureNetflixId' in cookies:
        return 'netflix'
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
                'required_cookies': ['sessionKey', 'routingHint', 'cf_clearance']
            },
            'tiktok': {
                'name': 'TikTok',
                'required_cookies': ['sessionid', 'sid_tt', 'uid_tt']
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
