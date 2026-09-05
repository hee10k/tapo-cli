#!/usr/bin/env python3

# DO NOT RUN ANY OF THIS CODE UNLESS YOU UNDERSTAND WHAT IT DOES
# I TAKE NO RESPONSIBILITY FOR ANYTHING, USE ON YOUR OWN RISK

# There are no sanity checks or checks for errors in this script. If it fails, if fails. Usually it doesn't fail. Just run it again or fix the error and submit a pull request. Be thankful you didn't have to reverse engineer Tapo's HMAC-SHA1 signature nightmare.

# Copyright Dimme 2023

import os
import sys
import subprocess
import tempfile
import click
import requests
import urllib3
import hashlib
import hmac
import base64
import uuid
import time
import json
import re
import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Ensure UTF-8 output on Windows consoles to prevent cp949 / charmap UnicodeEncodeErrors
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def sanitize_filename(name: str) -> str:
    """Sanitizes a string to make it safe for use as a directory or file name on Windows, macOS, and Linux."""
    if not name:
        return 'unnamed'
    # Strip characters invalid on Windows: < > : " / \ | ? * and ASCII control characters
    sanitized = re.sub(r'[\x00-\x1f\\/*?:"<>|]', '_', name)
    # Strip leading/trailing spaces and dots which are invalid on Windows
    sanitized = sanitized.strip(' .')
    # Check for Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        *(f'COM{i}' for i in range(1, 10)),
        *(f'LPT{i}' for i in range(1, 10))
    }
    if sanitized.upper() in reserved_names:
        sanitized = f"_{sanitized}_"
    return sanitized if sanitized else 'unnamed'


# Secrets extracted from the .apk
access_key = '4d11b6b9d5ea4d19a829adbb9714b057'
secret = '6ed7d97f3e73467f8a5bab90b577ba4c'

# Every request needs a uuid nonce and time, any value seems to work but let's not raise any suspicions.
nonce = str(uuid.uuid1())
now = str(int(time.time()))

# Yeah Tapo is using expired certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Weird MD5 implementation for the Content-Md5 header
def content_md5(content):
    return base64.b64encode(hashlib.md5(content.encode('UTF-8')).digest()).decode('UTF-8')

# Signature algorithm for the X-Authorization header
def signature(content, endpoint):
    payload = (content_md5(content) + '\n' + now + '\n' + nonce + '\n' + endpoint).encode('UTF-8')
    return hmac.new(secret.encode('UTF-8'), payload, hashlib.sha1).digest().hex()

# X-Authorization header contents
def x_authorization(content, endpoint):
    return 'Timestamp=' + now + ', Nonce=' + nonce + ', AccessKey=' + access_key + ', Signature=' + signature(content, endpoint)

# The global entry point for logging in. Your account is pinned to a regional
# server and this one only points us at it, see login().
login_url = 'https://n-wap-gw.tplinkcloud.com'

# Tapo Care is regional too. If we cannot tell which region an account belongs
# to we assume EU West, which is what this script used to hardcode for everyone.
default_region = 'euw1'

# Every URL Tapo hands us at login carries the region, e.g.
# https://n-use1-wap-gw.tplinkcloud.com or https://use1-account-api.i.tplinkcloud.com
def region(config):
    for key, pattern in (('appServerUrl', r'^https?://n-([a-z0-9]+)-wap[-.]'),
                         ('appServerUrlV2', r'^https?://n-([a-z0-9]+)-wap[-.]'),
                         ('accountApiUrl', r'^https?://([a-z0-9]+)-account-api[-.]')):
        match = re.match(pattern, config.get(key) or '')
        if match:
            return match.group(1)
    return default_region

# Where this account's Tapo Care videos live
def tapo_care_url(config):
    return 'https://' + region(config) + '-app-tapo-care.i.tplinknbu.com'

def config_path():
    return os.path.join(os.path.expanduser('~'), '.tapo-cli', '.config')

# Gets authorization token from ~/.tapo-cli/.config
def get_config():
    try:
        with open(config_path(), 'r', encoding='utf-8') as file:
            config = json.loads(file.read())
        token = config['token']
    except (IOError, OSError, ValueError, KeyError):
        print('Please login first.')
        exit(1)

    # Configs written by older versions have no tapoCareUrl, so work it out from
    # the other URLs they did save rather than making them login again.
    return (token, config.get('email', ''), config.get('appServerUrl') or login_url,
            config.get('tapoCareUrl') or tapo_care_url(config))

# The app gateway calls it error_code, the account endpoints call it errorCode
# and send it as a string. Returns 0 when Tapo is happy.
def error_code(obj):
    if not isinstance(obj, dict):
        return 0
    for key in ('error_code', 'errorCode'):
        if key in obj:
            try:
                return int(obj[key])
            except (TypeError, ValueError):
                return 1
    return 0

# Tapo's way of saying "login again"
def token_expired(obj):
    if not isinstance(obj, dict):
        return False
    if error_code(obj) == -20651:
        return True
    return 'token' in (str(obj.get('msg', '')) + ' ' + str(obj.get('errorMsg', ''))).lower()

# Print and die when we get an error from Tapo
def error(obj):
    print('Something went wrong:')
    print(json.dumps(obj, indent = 4) if isinstance(obj, (dict, list)) else obj)
    if token_expired(obj):
        print('\nYour access token is no longer valid. Run "tapo-cli.py login" to get a new one.')
    exit(1)

# Headers that the Android app is using with GET endpoints in general.
def headers_get(token):
    return {
        'Authorization' : 'ut|' + token,
        'X-App-Name' : 'TP-Link_Tapo_Android'
    }

# Headers that the Android app is using with POST endpoints in general.
def headers_post(content, endpoint):
    return {
        'Content-Md5' : content_md5(content),
        'X-Authorization' : x_authorization(content, endpoint),
        'Content-Type': 'application/json; charset=UTF-8',
        'User-Agent': 'Tapo CameraClient Android' if '/api/v2/common/passthrough' in endpoint else 'okhttp/3.12.13'
    }

# GET with my own settings (e.g. with Burp Proxy for debugging)
def get(url, params, headers):
    return json.loads(requests.get(url, params = params, headers = headers, verify = False).text)

# POST with my own settings (e.g. with Burp Proxy for debugging)
def post(url, data, headers):
    return json.loads(requests.post(url, data = data, headers = headers, verify = False).text)

# Downloads a file from the Internet and decrypts it
def download(url, key_b64, file_path, file_name):
    os.makedirs(file_path, exist_ok=True)

    res = requests.get(url)
    content = res.content

    if key_b64:
        key = base64.b64decode(key_b64)
        iv = content[:16]
        enc_data = content[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        dec_content = unpad(cipher.decrypt(enc_data), AES.block_size)
    else:
        dec_content = content

    target_full_path = os.path.join(file_path, file_name)
    temp_full_path = target_full_path + '.tmp'
    try:
        with open(temp_full_path, 'wb') as file:
            file.write(dec_content)
        if os.path.exists(target_full_path):
            try:
                os.remove(target_full_path)
            except OSError:
                pass
        os.replace(temp_full_path, target_full_path)
    except Exception:
        if os.path.exists(temp_full_path):
            try:
                os.remove(temp_full_path)
            except OSError:
                pass
        raise
    return len(dec_content)

def probe_endpoint_get(params, endpoint):
    token, null, null, app_server_url_get = get_config()
    url = app_server_url_get + endpoint
    res = get(url, params, headers_get(token))
    if error_code(res) != 0:
        error(res)
    return res

def probe_endpoint_post(content, endpoint):
    token, null, app_server_url_post, null = get_config()
    url = app_server_url_post + endpoint + '?token=' + token
    res = post(url, content, headers_post(content, endpoint))
    if error_code(res) != 0:
        error(res)
    return res['result']

# Anything that identifies you or lets someone act as you, stripped before we
# print a response so that debug output is safe to paste into a bug report.
secret_keys = ('token', 'refreshToken', 'cloudPassword', 'password', 'accountId',
               'email', 'mfaEmail', 'cloudUserName', 'nickname', 'MFAProcessId')

def redact(obj):
    if isinstance(obj, dict):
        return dict((key, '<redacted>' if key in secret_keys else redact(value)) for key, value in obj.items())
    if isinstance(obj, list):
        return [redact(value) for value in obj]
    return obj

debug_enabled = False

def debug(label, obj):
    if debug_enabled:
        print('\n[debug] ' + label)
        print(json.dumps(redact(obj), indent = 4))

# How the verification code reaches you. The login response lists the types the
# account supports in supportedMFATypes: 1 is a push notification to a Tapo app
# already bound to the account, 2 is email. A fresh terminalUUID like the one
# this script generates is bound to nothing, so push has nowhere to arrive.
mfa_push, mfa_email = 1, 2

mfa_type_names = {mfa_push: 'push notification to the Tapo app', mfa_email: 'email'}

# The push endpoint's name is known from the app. The email one is not, so these
# are tried in order by the probe-mfa command until Tapo accepts one.
mfa_endpoints = {
    mfa_push: ['/api/v2/account/getPushVC4TerminalMFA'],
    mfa_email: ['/api/v2/account/getEmailVC4TerminalMFA',
                '/api/v2/account/sendEmailVC4TerminalMFA',
                '/api/v2/account/getEmailVC4TerminalBind',
                '/api/v2/account/getVC4TerminalMFA',
                '/api/v2/account/getEmailVerifyCode'],
}

# POSTs to one of the unauthenticated account endpoints and returns its result
def account_post(base_url, endpoint, content):
    debug('POST ' + base_url + endpoint, content)
    content = json.dumps(content)
    res = post(base_url + endpoint, content, headers_post(content, endpoint))
    debug('response from ' + endpoint, res)
    if error_code(res) != 0:
        error(res)
    result = res.get('result')
    return result if isinstance(result, dict) else {}

# Midnight-to-midnight window covering the last X days. Local time, because that
# is the clock Tapo filters on and reports eventLocalTime in.
def time_range(days):
    today = datetime.datetime.now().replace(hour = 0, minute = 0, second = 0, microsecond = 0)
    start_time = (today - datetime.timedelta(days = days)).strftime('%Y-%m-%d %H:%M:%S')
    end_time = (today + datetime.timedelta(days = 1)).strftime('%Y-%m-%d %H:%M:%S')
    return start_time, end_time

# An empty listing is usually a region or a subscription problem, so say so
# instead of quietly printing zeroes.
def no_videos_hint(app_server_url_get):
    print('\nNo videos were found. Worth checking:')
    print(' - Only Tapo Care cloud recordings can be listed here, not clips stored on the camera SD card.')
    print(' - Try a larger --days value.')
    print(' - We looked on ' + app_server_url_get + '. If your account belongs to another')
    print('   region, delete ' + config_path() + ' and login again.')

@click.group()
def tapo():
    """Command-line application for batch-downloading your videos from the Tapo TP-Link Cloud."""
    pass

@click.command()
@click.option('--username', default="email@example.com", prompt="Username", help='Your Tapo TP-Link username.')
@click.option('--password', prompt="Password", hide_input=True, help='Your Tapo TP-Link password. Prefer the prompt over this option, which leaks into shell history.')
@click.option('--mfa-type', default=None, type=int, help='How to receive the MFA code: 1 for a Tapo app push notification, 2 for email.')
@click.option('--debug', 'show_debug', is_flag=True, default=False, help='Print the requests and responses, with your credentials redacted.')
def login(username, password, mfa_type, show_debug):
    """Authenticates a user towards the TP-Link Tapo Cloud."""
    global debug_enabled
    debug_enabled = show_debug
    terminal_uuid = str(uuid.uuid1()).replace('-','').upper()

    base_url = login_url
    endpoint = '/api/v2/account/login'
    content = {"appType":"TP-Link_Tapo_Android","appVersion":"2.12.705","cloudPassword":password,"cloudUserName":username,"platform":"Android 12","refreshTokenNeeded":False,"terminalMeta":"1","terminalName":"Tapo CLI","terminalUUID":terminal_uuid}
    result = account_post(base_url, endpoint, content)

    # Accounts outside the region of the global entry point get bounced with
    # -20212 "Incorrect service entry address", which names the server to use.
    if error_code(result) == -20212 and result.get('appServerUrl'):
        base_url = result['appServerUrl']
        print('Your account belongs to ' + base_url + ', logging in there instead.')
        result = account_post(base_url, endpoint, content)

    # Login but with extra steps
    if 'MFAProcessId' in result:
        mfa_process_id = result['MFAProcessId']
        supported = result.get('supportedMFATypes') or [mfa_push]
        if mfa_type is None:
            mfa_type = supported[0]
        if mfa_type not in supported:
            print('Your account does not support MFA type ' + str(mfa_type) + '. It supports: '
                  + ', '.join(str(one) + ' (' + mfa_type_names.get(one, 'unknown') + ')' for one in supported))
            exit(1)

        print('Requesting an MFA code by ' + mfa_type_names.get(mfa_type, 'type ' + str(mfa_type)) + '.')
        content = {"appType":"TP-Link_Tapo_Android","cloudPassword":password,"cloudUserName":username,"terminalUUID":terminal_uuid}
        sent = account_post(base_url, mfa_endpoints[mfa_type][0], content)

        # This request is what actually sends the code. Its verdict used to be
        # thrown away, which left you staring at a prompt for a code that was
        # never going to arrive.
        if error_code(sent) != 0:
            print('\nTapo would not send the code:')
            print(json.dumps(redact(sent), indent = 4))
            if len(supported) > 1:
                print('\nYour account also supports: ' + ', '.join(
                    str(one) + ' (' + mfa_type_names.get(one, 'unknown') + ')' for one in supported if one != mfa_type))
                print('Try again with --mfa-type ' + str([one for one in supported if one != mfa_type][0]) + '.')
            exit(1)

        if mfa_type == mfa_push:
            print('Check your Tapo app. The push only arrives if this terminal is already')
            print('bound to your account, so if nothing shows up try --mfa-type 2 for email.')
        else:
            print('Check your email (including the spam folder) for the code.')

        mfa_code = str(input('MFA Code (no spaces or dashes): '))

        content = {"appType":"TP-Link_Tapo_Android","cloudUserName":username,"code":mfa_code,"MFAProcessId":mfa_process_id,"MFAType":mfa_type,"terminalBindEnabled":True}
        result = account_post(base_url, '/api/v2/account/checkMFACodeAndLogin', content)

    # Go by errorCode only. errorMsg is localised, so comparing it against the
    # English "Success" used to throw away logins that had in fact succeeded.
    if error_code(result) != 0 or 'token' not in result:
        error(result)

    # Remember which region this account lives in, so that the other commands
    # ask the right servers instead of assuming EU West.
    result['appServerUrl'] = result.get('appServerUrl') or base_url
    result['tapoCareUrl'] = tapo_care_url(result)

    file_path = os.path.dirname(config_path())
    os.makedirs(file_path, exist_ok=True)
    with open(config_path(), 'w', encoding='utf-8') as file:
        file.write(json.dumps(result, indent = 4))
    print('Access token saved in ' + config_path())

@click.command()
@click.option('--username', default="email@example.com", prompt="Username", help='Your Tapo TP-Link username.')
@click.option('--password', prompt="Password", hide_input=True, help='Your Tapo TP-Link password.')
@click.option('--mfa-type', default=2, type=int, help='Which delivery channel to probe. 2 is email.')
def probe_mfa(username, password, mfa_type):
    """Finds which endpoint sends an MFA code, for when the push never arrives."""
    global debug_enabled
    debug_enabled = True
    terminal_uuid = str(uuid.uuid1()).replace('-','').upper()

    base_url = login_url
    endpoint = '/api/v2/account/login'
    content = {"appType":"TP-Link_Tapo_Android","appVersion":"2.12.705","cloudPassword":password,"cloudUserName":username,"platform":"Android 12","refreshTokenNeeded":False,"terminalMeta":"1","terminalName":"Tapo CLI","terminalUUID":terminal_uuid}
    result = account_post(base_url, endpoint, content)

    if error_code(result) == -20212 and result.get('appServerUrl'):
        base_url = result['appServerUrl']
        result = account_post(base_url, endpoint, content)

    if 'MFAProcessId' not in result:
        print('\nThis account did not ask for MFA, so there is nothing to probe.')
        return

    print('\nAccount supports MFA types: ' + ', '.join(
        str(one) + ' (' + mfa_type_names.get(one, 'unknown') + ')' for one in result.get('supportedMFATypes', [])))

    # Stop at the first endpoint Tapo accepts. Each attempt is a real request
    # against your account, so we do not keep hammering after one works.
    content = {"appType":"TP-Link_Tapo_Android","cloudPassword":password,"cloudUserName":username,"terminalUUID":terminal_uuid}
    for candidate in mfa_endpoints.get(mfa_type, []):
        print('\nTrying ' + candidate)
        res = post(base_url + candidate, json.dumps(content), headers_post(json.dumps(content), candidate))
        print(json.dumps(redact(res), indent = 4))
        # Both layers have to be happy: the envelope can say error_code 0 while
        # the result inside carries the real refusal.
        if error_code(res) == 0 and error_code(res.get('result')) == 0:
            print('\n==> ' + candidate + ' was accepted. Check whether a code actually arrived.')
            print('    If it did, login with: ./tapo-cli.py login --mfa-type ' + str(mfa_type))
            return

    print('\nNone of the candidate endpoints were accepted. Paste this output into the issue.')

@click.command()
def account_info():
    """Lists information about your account."""
    null, email, null, null = get_config()
    endpoint = '/api/v2/account/getAccountInfo'

    # Vulnerabilities found here, it will return:
    # - 'Account not found' if the account is not found
    # - 'Token incorrect' if the account exists but you are not logged in as that user
    # Which makes it possible to enumerate users with Tapo accounts

    content = '{"cloudUserName":"' + email + '"}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

@click.command()
def devices():
    """Lists your first 20 Tapo devices."""
    get_config() # Checks if logged in
    endpoint = '/api/v2/common/getDeviceListByPage'
    content = '{"deviceTypeList":["SMART.TAPOPLUG","SMART.TAPOBULB","SMART.IPCAMERA","SMART.TAPOROBOVAC","SMART.TAPOHUB","SMART.TAPOSENSOR","SMART.TAPOSWITCH"],"index":0,"limit":20}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

@click.command()
def devices_limit():
    """Lists the device limits for your account by device type."""
    get_config() # Checks if logged in
    endpoint = '/api/v2/common/batchGetDeviceUserNumberLimit'
    content = '{"deviceTypeList":["SMART.TAPOPLUG","SMART.TAPOBULB","SMART.IPCAMERA","SMART.TAPOROBOVAC","SMART.TAPOHUB","SMART.TAPOSENSOR","SMART.TAPOSWITCH"]}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

@click.command()
def devices_info():
    """Lists A LOT of parameters for your devices."""
    get_config() # Checks if logged in
    endpoint = '/api/v2/common/getDeviceListByPage'
    content = '{"deviceTypeList":["SMART.TAPOPLUG","SMART.TAPOBULB","SMART.IPCAMERA","SMART.TAPOROBOVAC","SMART.TAPOHUB","SMART.TAPOSENSOR","SMART.TAPOSWITCH"],"index":0,"limit":20}'
    devs = probe_endpoint_post(content, endpoint)

    endpoint = '/api/v2/common/passthrough'
    for dev in devs['deviceList']:
        print('\nGetting ' + dev['alias'] + ':')
        content = '{"deviceId":"' + dev['deviceId'] + '","requestData":{"method":"multipleRequest","params":{"requests":[{"method":"getDeviceInfo","params":{"device_info":{"name":["basic_info"]}}},{"method":"getLastAlarmInfo","params":{"system":{"name":["last_alarm_info"]}}},{"method":"getAppComponentList","params":{"app_component":{"name":["app_component_list"]}}},{"method":"getVideoCapability","params":{"video_capability":{"name":["main","minor"]}}},{"method":"checkFirmwareVersionByCloud","params":{"cloud_config":{"check_fw_version":"null"}}},{"method":"getCloudConfig","params":{"cloud_config":{"name":["upgrade_info"]}}},{"method":"getP2PSharePassword","params":{"user_management":{"get_p2p_sharepwd":{}}}}]}}}'
        try:
            res = probe_endpoint_post(content, endpoint)
            print(json.dumps(res, indent = 4))
        except:
            continue

@click.command()
def service_urls():
    """Lists URLs for various Tapo services."""
    get_config() # Checks if logged in 
    endpoint = '/api/v2/common/getAppServiceUrl'
    content = '{"serviceIds":["nbu.iot-app-server.app","nbu.iot-cloud-gateway.app","nbu.iot-security.appdevice","cipc.api"]}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

@click.command()
def notifications():
    """Lists notifications from your phone app."""
    get_config() # Checks if logged in
    endpoint = '/api/v2/common/getAppNotificationByPage'

    # Vulnerabilities found here:
    # - deviceToken should not be allowed to be empty
    # - terminalUUID is not required if replaced by a single "'"
    # Thankfully the API doesn't return any screenshots for other users

    content = '{"appType":"TP-Link_Tapo_Android","contentVersion":2,"deviceToken":"","direction":"asc","index":0,"indexTime":' + now + ',"limit":50,"locale":"en_US","mobileType":"ANDROID","msgTypes":["UNKNOWN_NOTIFICATION_MSG","tapoShareLaunch","tapoNewFirmware","Motion","Audio","BabyCry","tapoFfsNewDeviceFound","smartTapoDeviceActivity","PersonDetected","PersonEnhanced","tapoCameraSDNeedInitialization","tapoCameraSDInsufficientStorage","tapoCameraAreaIntrusionDetection","tapoCameraLinecrossingDetection","tapoCameraCameraTampering","tapoGlassBreakingDetected","tapoSmokeAlarmDetected","tapoMeowDetected","tapoBarkDetected","TAPO_CARE_TRIAL_EXPIRING_IN_3_DAYS","TAPO_CARE_TRIAL_EXPIRED","TAPO_CARE_SUBSCRIPTION_EXPIRING_IN_3_DAYS","TAPO_CARE_SUBSCRIPTION_EXPIRED","TAPO_CARE_SUBSCRIPTION_PAYMENT_FAILED","tapoHubTriggered","tapoContactSensorTriggered","tapoMotionSensorTriggered","tapoSmartButtonTriggered","tapoSmartSwitchTriggered","tapoDeviceLowBattery","tapoSensorFrequentlyTriggered","brandPromotion","marketPromotion","announcement","userResearch","tapoDeviceOverheat","tapoDeviceOverheatRelieve","videosummaryGenerated","videosummaryCanCreateFromClips","tapoCareWeeklyReport","tapoCareWeeklyReportNewFeature","BatteryEmpty","BatteryFullyCharged","PowerSavingModeEnabled","CameraLowBattery","PetDetected","VehicleDetected","deliverPackageDetected","pickUpPackageDetected","antiTheft","ringEvent","missRingEvent","tapoSensorWaterLeakDetected","tapoSensorWaterLeakSolved","tapoSensorTempTooWarm","tapoSensorTempTooCool","tapoSensorTooHumid","tapoSensorTooDry","lensMaskChargingEnabled","tapoDevicePowerProtection","tpSimpleSetup","other","robotBatteryExceptionEvent","robotCleanRelativeEvent","robotLocateFailEvent","robotIssueDetected"],"terminalUUID":"\'"}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

@click.command()
def subscriptions():
    """Lists your email subscriptions."""
    null, email, null, null = get_config() # Checks if logged in
    endpoint = '/api/v2/account/getTopicSubscription'
    content = '{"email":"' + email + '","productLine":"NBU"}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

@click.command()
def mfa_status():
    """Lists your MFA status."""
    get_config() # Checks if logged in
    endpoint = '/api/v2/account/getMFAFeatureStatus'
    content = '{}'
    res = probe_endpoint_post(content, endpoint)
    print(json.dumps(res, indent = 4))

def format_time_ago(event_local_time_str):
    """Calculates days ago from today for display (e.g. '오늘', '1일 전', '30일 전 (D-30)')."""
    try:
        event_dt = datetime.datetime.strptime(event_local_time_str, '%Y-%m-%d %H:%M:%S')
        today = datetime.datetime.now().date()
        diff_days = (today - event_dt.date()).days
        if diff_days <= 0:
            return "오늘"
        elif diff_days == 1:
            return "1일 전"
        else:
            return f"{diff_days}일 전 (D-{diff_days})"
    except Exception:
        return "알 수 없음"

def format_file_size(num_bytes):
    """Formats bytes into human-readable MB / KB."""
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    elif num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes} B"

def iter_videos(device_id, start_time, end_time, order='asc'):
    """Yields (total_count, current_index, video_item) in streaming pages from Tapo API."""
    page = 0
    page_size = 1000
    endpoint = '/v2/videos/list'
    yielded_count = 0
    total = None

    while True:
        params = {
            'deviceId': device_id,
            'page': page,
            'pageSize': page_size,
            'order': order,
            'startTime': start_time,
            'endTime': end_time
        }
        res = probe_endpoint_get(params, endpoint)
        if total is None:
            total = res.get('total', 0)

        items = res.get('index', [])
        if not items:
            break

        for item in items:
            yielded_count += 1
            yield total, yielded_count, item

        if yielded_count >= total:
            break
        page += 1

def fetch_all_videos(device_id, start_time, end_time, order='asc'):
    """Fetches all videos for a device between start_time and end_time, handling pagination."""
    all_videos = []
    total = 0
    for tot, idx, video in iter_videos(device_id, start_time, end_time, order=order):
        total = tot
        all_videos.append(video)
    return total, all_videos

def filter_devices(devices, camera_query):
    """Filters device list based on camera query (name/alias or device ID)."""
    if not camera_query or camera_query.strip().lower() in ('all', ''):
        return devices

    selected_queries = [q.strip().lower() for q in camera_query.split(',') if q.strip()]
    matched = []

    for dev in devices:
        alias = dev.get('alias', '').strip().lower()
        dev_id = dev.get('deviceId', '').strip().lower()

        for q in selected_queries:
            if q == alias or q == dev_id or (len(q) >= 2 and q in alias):
                if dev not in matched:
                    matched.append(dev)
                break

    return matched

@click.command()
@click.option('--days', default=1, type=int, help='Last X days which you want to list videos for (default: 1).')
@click.option('--camera', '-c', default=None, help='Filter by camera name (alias) or device ID. Comma-separated for multiple, or "all".')
def list_videos(days, camera):
    """Lists videos for the last X days."""
    get_config() # Checks if logged in
    endpoint = '/api/v2/common/getDeviceListByPage'
    content = '{"deviceTypeList":["SMART.IPCAMERA"],"index":0,"limit":20}'
    devs = probe_endpoint_post(content, endpoint)

    device_list = filter_devices(devs.get('deviceList', []), camera)
    if not device_list:
        available = [d.get('alias', 'unknown') for d in devs.get('deviceList', [])]
        print(f"No cameras matched '{camera}'. Available cameras: {', '.join(available)}")
        return
    
    start_time, end_time = time_range(days)

    grand_total = 0
    for dev in device_list:
        total, videos = fetch_all_videos(dev['deviceId'], start_time, end_time, order='asc')
        grand_total += total
        print('\nFound ' + str(total) + ' videos for ' + dev['alias'] + ':')
        if videos:
            print(f"Available range: {videos[0]['eventLocalTime']} (earliest) ~ {videos[-1]['eventLocalTime']} (latest)")
        for video in videos:
            print(video['eventLocalTime'], end = ", ")
        if total > 0: print('')

    if grand_total == 0:
        null, null, null, app_server_url_get = get_config()
        no_videos_hint(app_server_url_get)

@click.command()
@click.option('--days', default=1, type=int, help='Last X days which you want to download videos for (default: 1).')
@click.option('--path', default="~/", help='Path where you want your videos to be downloaded (default: ~/ which creates subdirectories by camera/date).')
@click.option('--overwrite', default=0, type=int, help='Overwrite files if already existing (default: 0 = skip duplicate/existing, 1 = overwrite).')
@click.option('--camera', '-c', default=None, help='Filter by camera name (alias) or device ID. Comma-separated for multiple, or "all".')
def download_videos(days, path, overwrite, camera):
    """Downloads videos starting from the oldest available date with smart deduplication and live progress."""
    get_config() # Checks if logged in
    
    base_dir = os.path.abspath(os.path.expanduser(path))
    
    endpoint = '/api/v2/common/getDeviceListByPage'
    content = '{"deviceTypeList":["SMART.IPCAMERA"],"index":0,"limit":20}'
    devs = probe_endpoint_post(content, endpoint)

    device_list = filter_devices(devs.get('deviceList', []), camera)
    if not device_list:
        available = [d.get('alias', 'unknown') for d in devs.get('deviceList', [])]
        print(f"No cameras matched '{camera}'. Available cameras: {', '.join(available)}")
        return []
    
    start_time, end_time = time_range(days)

    result = []
    seen_video_uuids = set()

    for dev in device_list:
        device_alias = dev.get('alias', 'unknown')
        device_folder = sanitize_filename(device_alias)
        
        print("\n" + "=" * 80)
        print(f" ▶ 카메라: '{device_alias}' (가장 오래된 날짜부터 순차 다운로드 시작)")
        print("=" * 80, flush=True)

        downloaded_count = 0
        skipped_count = 0
        total_videos = 0

        # Stream videos starting from oldest date (order='asc')
        for total, current_idx, video in iter_videos(dev['deviceId'], start_time, end_time, order='asc'):
            total_videos = total
            video_time = video.get('eventLocalTime', '')
            time_ago_str = format_time_ago(video_time)
            pct = (current_idx / total * 100.0) if total > 0 else 0.0

            progress_prefix = f"[{current_idx:>{len(str(total))}}/{total:,}] ({pct:>5.1f}%) [{time_ago_str}] {video_time}"

            # 1. Deduplicate by video UUID within this session
            video_uuid = video.get('uuid', '')
            if video_uuid:
                if video_uuid in seen_video_uuids:
                    skipped_count += 1
                    continue
                seen_video_uuids.add(video_uuid)

            url = video['video'][0]['uri']
            key_b64 = False

            if 'encryptionMethod' in video['video'][0]:
                method = video['video'][0]['encryptionMethod']
                if method != "AES-128-CBC":
                    print(f"\n[오류] 지원되지 않는 암호화 방식: {method}")
                    exit(1)
                key_b64 = video['video'][0]['decryptionInfo']['key']

            date_folder = datetime.datetime.strptime(video_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
            target_dir = os.path.join(base_dir, device_folder, date_folder)
            file_name = video_time.replace(':', '-') + '.mp4'
            full_path = os.path.join(target_dir, file_name)

            # 2. Check duplicate / already exists
            if os.path.exists(full_path) and overwrite == 0:
                file_sz = os.path.getsize(full_path)
                if file_sz > 0:
                    print(f"{progress_prefix} -> [건너뜀] 이미 존재함 ({format_file_size(file_sz)})", flush=True)
                    skipped_count += 1
                    result.append({'file': full_path, 'device': device_alias, 'new_video': False, 'video': video})
                    continue
                else:
                    try:
                        os.remove(full_path)
                    except OSError:
                        pass

            # 3. Download
            print(f"{progress_prefix} -> [다운로드 중...] ", end="", flush=True)
            bytes_saved = download(url, key_b64, target_dir, file_name)
            print(f"완료 ({format_file_size(bytes_saved)})", flush=True)
            downloaded_count += 1
            result.append({'file': full_path, 'device': device_alias, 'new_video': True, 'video': video})

        if total_videos == 0:
            print(f"저장된 비디오가 없습니다.")
        else:
            print("\n" + "-" * 80)
            print(f" ▶ '{device_alias}' 작업 완료 요약:")
            print(f"   • 총 비디오 수    : {total_videos:,}개")
            print(f"   • 신규 다운로드   : {downloaded_count:,}개")
            print(f"   • 중복 건너뜀     : {skipped_count:,}개")
            print("-" * 80 + "\n", flush=True)

    if not result:
        null, null, null, app_server_url_get = get_config()
        no_videos_hint(app_server_url_get)

    return result

def parse_clip_timestamp(filename_or_path):
    """Extracts start datetime from filename like '2026-09-05 09-48-35.mp4' or '2026-09-05 09-48-35_xxx.mp4'."""
    basename = os.path.basename(filename_or_path)
    match = re.search(r'(\d{4}-\d{2}-\d{2})[ _T](\d{2})[-:](\d{2})[-:](\d{2})', basename)
    if match:
        date_part = match.group(1)
        h, m, s = match.group(2), match.group(3), match.group(4)
        try:
            return datetime.datetime.strptime(f"{date_part} {h}:{m}:{s}", '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    return None

def get_video_duration(file_path):
    """Gets video duration in seconds using ffprobe, or defaults to 60.0s if unavailable."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass
    return 60.0

def group_continuous_clips(clips, max_gap_seconds=60):
    """Groups clips where the gap between consecutive clips is <= max_gap_seconds."""
    if not clips:
        return []

    sorted_clips = sorted(clips, key=lambda c: c['start_time'])
    groups = []
    current_group = []

    for clip in sorted_clips:
        if not current_group:
            current_group.append(clip)
            continue

        prev_clip = current_group[-1]
        gap = (clip['start_time'] - prev_clip['end_time']).total_seconds()

        # Allow slight overlap (-5s) up to max_gap_seconds
        if -5.0 <= gap <= max_gap_seconds:
            current_group.append(clip)
        else:
            groups.append(current_group)
            current_group = [clip]

    if current_group:
        groups.append(current_group)

    return groups

def merge_clip_group_ffmpeg(clips, output_file):
    """Merges a list of mp4 clips using ffmpeg concat demuxer without re-encoding."""
    if not clips:
        return False

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        temp_list_path = f.name
        for clip in clips:
            safe_path = os.path.abspath(clip['path']).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        temp_output = output_file + '.tmp.mp4'
        cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-f', 'concat', '-safe', '0',
            '-i', temp_list_path,
            '-c', 'copy',
            temp_output
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except OSError:
                    pass
            os.replace(temp_output, output_file)
            return True
        else:
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except OSError:
                    pass
            return False
    finally:
        if os.path.exists(temp_list_path):
            try:
                os.remove(temp_list_path)
            except OSError:
                pass

@click.command()
@click.option('--path', default="~/", help='Base directory where downloaded videos are stored (default: ~/).')
@click.option('--camera', '-c', default=None, help='Filter by camera folder name (e.g. "정우방").')
@click.option('--max-gap', default=60, type=int, help='Maximum gap in seconds between clips to be considered continuous (default: 60s).')
@click.option('--output-dir', default=None, help='Custom output directory for merged videos (default: creates "merged" subfolder).')
@click.option('--delete-source', is_flag=True, default=False, help='Delete original fragmented clips after successful merge.')
def merge_videos(path, camera, max_gap, output_dir, delete_source):
    """Merges continuous CCTV clips if the time gap between them is <= max-gap seconds."""
    base_dir = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(base_dir):
        print(f"[오류] 지정한 경로를 찾을 수 없습니다: {base_dir}")
        return

    # Check ffmpeg availability
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception:
        print("[오류] ffmpeg가 설치되어 있지 않거나 PATH에 등록되어 있지 않습니다.")
        print("ffmpeg를 설치해주세요 (Windows: 'scoop install ffmpeg' 또는 'winget install Gyan.FFmpeg').")
        return

    # Find camera directories
    camera_dirs = []
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and item.lower() != 'merged':
            if not camera or camera.lower() in item.lower():
                camera_dirs.append((item, item_path))

    if not camera_dirs:
        print(f"'{base_dir}'에서 비디오가 저장된 카메라 폴더를 찾을 수 없습니다.")
        return

    print("\n" + "=" * 80)
    print(f" [연속 CCTV 비디오 병합 작업 시작]")
    print(f" • 기준 경로 : {base_dir}")
    print(f" • 최대 연속 간격 : {max_gap}초 이하 (설정 간격 이하 시 이어붙임)")
    print("=" * 80)

    total_merged_groups = 0
    total_clips_merged = 0

    for cam_name, cam_path in camera_dirs:
        print(f"\n▶ 카메라: '{cam_name}' 탐색 중...")
        
        # Scan date folders (e.g. 2026-09-05)
        date_dirs = [d for d in os.listdir(cam_path) if os.path.isdir(os.path.join(cam_path, d)) and d.lower() != 'merged']
        date_dirs.sort()

        cam_merged_count = 0
        cam_clips_count = 0

        for date_str in date_dirs:
            date_path = os.path.join(cam_path, date_str)
            files = [f for f in os.listdir(date_path) if f.lower().endswith('.mp4') and not f.endswith('.tmp.mp4')]
            
            clips = []
            for f in files:
                f_path = os.path.join(date_path, f)
                ts = parse_clip_timestamp(f)
                if ts:
                    dur = get_video_duration(f_path)
                    clips.append({
                        'path': f_path,
                        'filename': f,
                        'start_time': ts,
                        'duration': dur,
                        'end_time': ts + datetime.timedelta(seconds=dur)
                    })

            if not clips:
                continue

            groups = group_continuous_clips(clips, max_gap_seconds=max_gap)

            for group in groups:
                if len(group) < 2:
                    # Single isolated clip, no need to merge
                    continue

                first_clip = group[0]
                last_clip = group[-1]
                start_str = first_clip['start_time'].strftime('%Y-%m-%d %H-%M-%S')
                end_time_str = last_clip['end_time'].strftime('%H-%M-%S')
                total_duration_sec = sum(c['duration'] for c in group)
                total_min = int(total_duration_sec // 60)
                total_sec = int(total_duration_sec % 60)

                # Output directory
                if output_dir:
                    out_date_dir = os.path.join(os.path.abspath(os.path.expanduser(output_dir)), cam_name, date_str)
                else:
                    out_date_dir = os.path.join(cam_path, 'merged', date_str)

                merged_filename = f"{start_str}_to_{end_time_str} ({len(group)}clips, {total_min}m{total_sec}s).mp4"
                merged_output_path = os.path.join(out_date_dir, merged_filename)

                # Check if already merged
                if os.path.exists(merged_output_path) and os.path.getsize(merged_output_path) > 0:
                    print(f"  [이미 병합됨] {date_str} {start_str} ~ {end_time_str} ({len(group)}개 클립)")
                    continue

                print(f"  [병합 중] {date_str} {start_str} ~ {end_time_str} ({len(group)}개 클립, {total_min}분 {total_sec}초)... ", end="", flush=True)
                success = merge_clip_group_ffmpeg(group, merged_output_path)
                if success:
                    merged_size = os.path.getsize(merged_output_path)
                    print(f"완료 ({format_file_size(merged_size)})", flush=True)
                    cam_merged_count += 1
                    cam_clips_count += len(group)

                    if delete_source:
                        for c in group:
                            try:
                                os.remove(c['path'])
                            except OSError:
                                pass
                else:
                    print("실패", flush=True)

        total_merged_groups += cam_merged_count
        total_clips_merged += cam_clips_count
        print(f"  >> '{cam_name}' 병합 결과: {cam_merged_count}개 연속 영상 생성 (총 {cam_clips_count}개 클립 병합)")

    print("\n" + "=" * 80)
    print(f" [전체 병합 작업 완료]")
    print(f" • 새로 생성된 연속 비디오 : {total_merged_groups:,}개")
    print(f" • 병합된 총 원본 클립 수 : {total_clips_merged:,}개")
    print("=" * 80 + "\n")

tapo.add_command(login, 'login')
tapo.add_command(probe_mfa, 'probe-mfa')
tapo.add_command(account_info, 'list-account-info')
tapo.add_command(devices_limit, 'list-devices-limit')
tapo.add_command(devices_info, 'list-devices-info')
tapo.add_command(devices, 'list-devices')
tapo.add_command(service_urls, 'list-service-urls')
tapo.add_command(notifications, 'list-notifications')
tapo.add_command(subscriptions, 'list-subscriptions')
tapo.add_command(mfa_status, 'list-mfa-status')
tapo.add_command(list_videos, 'list-videos')
tapo.add_command(download_videos, 'download-videos')
tapo.add_command(merge_videos, 'merge-videos')

if __name__ == '__main__':
    tapo()
