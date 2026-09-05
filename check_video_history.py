"""Inspect all Tapo cloud videos and check the available download date range."""
import os
import sys
import json
import datetime
import importlib.util
import requests

# Ensure UTF-8 console output on Windows
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

script_path = os.path.join(os.path.dirname(__file__), 'tapo-cli.py')
spec = importlib.util.spec_from_file_location("tapo_core", script_path)
tapo_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tapo_core)

def check_history(days=180):
    try:
        token, email, app_server_url, tapo_care_url = tapo_core.get_config()
    except SystemExit:
        print("\n[!] 로그인 정보가 없습니다. 먼저 'tapo login' 또는 'python tapo-cli.py login'을 실행해주세요.")
        return

    print(f"로그인 계정: {email}")
    print(f"조회 기간: 최근 {days}일 기준 탐색 중...\n")

    endpoint = '/api/v2/common/getDeviceListByPage'
    content = '{"deviceTypeList":["SMART.IPCAMERA"],"index":0,"limit":20}'
    try:
        devs = tapo_core.probe_endpoint_post(content, endpoint)
    except Exception as e:
        print(f"기기 목록을 불러오는 중 오류 발생: {e}")
        return

    device_list = devs.get('deviceList', [])
    if not device_list:
        print("계정에 연결된 IP 카메라 기기를 찾을 수 없습니다.")
        return

    start_time, end_time = tapo_core.time_range(days)
    video_endpoint = tapo_care_url + '/v2/videos/list'
    headers = tapo_core.headers_get(token)

    results = []

    for dev in device_list:
        alias = dev.get('alias', 'Unknown Camera')
        device_id = dev.get('deviceId', '')

        # Query latest (order=desc)
        params_desc = {
            'deviceId': device_id,
            'page': 0,
            'pageSize': 10,
            'order': 'desc',
            'startTime': start_time,
            'endTime': end_time
        }
        res_desc = requests.get(video_endpoint, headers=headers, params=params_desc, verify=False).json()
        total = res_desc.get('total', 0)

        if total == 0 or not res_desc.get('index'):
            results.append({
                'alias': alias,
                'device_id': device_id,
                'total': 0,
                'earliest': None,
                'latest': None,
                'days_span': 0
            })
            continue

        latest_time = res_desc['index'][0]['eventLocalTime']

        # Query earliest (order=asc)
        params_asc = {
            'deviceId': device_id,
            'page': 0,
            'pageSize': 10,
            'order': 'asc',
            'startTime': start_time,
            'endTime': end_time
        }
        res_asc = requests.get(video_endpoint, headers=headers, params=params_asc, verify=False).json()
        earliest_time = res_asc['index'][0]['eventLocalTime']

        # Calculate retention span
        dt_earliest = datetime.datetime.strptime(earliest_time, '%Y-%m-%d %H:%M:%S')
        dt_latest = datetime.datetime.strptime(latest_time, '%Y-%m-%d %H:%M:%S')
        span_days = (dt_latest - dt_earliest).days + 1

        results.append({
            'alias': alias,
            'device_id': device_id,
            'total': total,
            'earliest': earliest_time,
            'latest': latest_time,
            'days_span': span_days
        })

    print("=" * 70)
    print(" [카메라별 비디오 다운로드 가능 기간 및 현황]")
    print("=" * 70)
    for r in results:
        print(f"\n▶ 카메라: '{r['alias']}' (기기 ID: {r['device_id']})")
        if r['total'] > 0:
            print(f"  • 다운로드 가능한 총 비디오 수 : {r['total']:,}개")
            print(f"  • 다운로드 가능 시작 시점 (가장 오래된 비디오) : {r['earliest']}")
            print(f"  • 최근 비디오 시점 : {r['latest']}")
            print(f"  • 실제 보관 일수 범위 : 약 {r['days_span']}일간의 영상 보관 중")
        else:
            print(f"  • 저장된 클라우드 비디오 없음")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    days = 180
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            pass
    check_history(days)
