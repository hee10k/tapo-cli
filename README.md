# tapo-cli: Tapo TP-Link Cloud Video Downloader & Merger

[한국어 매뉴얼 (Korean Guide)](#한국어-매뉴얼-korean-user-manual) | [English Guide](#english-guide)

---

<a name="한국어-매뉴얼-korean-user-manual"></a>
# 📖 한국어 매뉴얼 (Korean User Manual)

`tapo-cli`는 TP-Link Tapo 클라우드에 저장된 CCTV 녹화 비디오를 손쉽게 대량 다운로드하고, 잘게 쪼개진 연속 녹화 클립을 무손실로 하나로 이어붙여 관리할 수 있는 크로스 플랫폼 CLI 도구입니다.

---

## 🚀 주요 기능 (Key Features)

1. **초고속 멀티스레드 병렬 다운로드 (`--concurrency` / `-w`, 기본값: 8)**
   - `ThreadPoolExecutor`를 활용하여 여러 비디오를 동시에 병렬로 다운로드하고 복호화합니다.
   - 단일 스레드 대비 **5배~10배 이상 비약적으로 빠른 다운로드 속도**를 제공합니다.
2. **가장 오래된 영상부터 순차 스트리밍 (Oldest-First Streaming)**
   - 수만 개의 비디오 목록 전체 조회를 기다리지 않고, **가장 오래된 날짜/시각부터 즉시 순차적으로 다운로드를 시작**합니다 (`order='asc'`).
3. **초고속 스마트 중복 제거 (Instant Pre-check Deduplication)**
   - 스레드 풀에 진입하기 전 로컬 파일의 존재 및 크기를 즉시 검사하여, 이미 다운로드된 수천 개의 파일은 **수 초 만에 빠르게 스킵**하고 미다운로드 구간부터 곧바로 다운로드합니다.
   - 0바이트 손상 파일은 자동으로 감지하여 재다운로드합니다.
4. **연속 CCTV 클립 무손실 병합 (`merge-videos`)**
   - 모션 감지로 인해 1~3분 단위로 잘게 분할 저장된 영상들을 **설정 시간 간격(기본값: 60초) 이하**일 때 하나의 긴 영상으로 묶어 병합합니다.
   - `ffmpeg concat demuxer`(`-c copy`)를 사용하여 재인코딩 화질 손실 없이 **수 초 만에 초고속 무손실 병합**합니다.
   - `--delete-source` 옵션으로 병합 완료 후 원본 조각 파일을 자동 정리할 수 있습니다.
5. **실시간 상세 진행도 및 D-Day 표시**
   - `[현재/전체] (진행률%) [며칠 전 영상인지 (예: D-20)] [촬영 시각] -> 상태 (용량)` 형식으로 실시간 콘솔에 정렬 출력됩니다.
6. **카메라 선택 필터링 (`--camera` / `-c`)**
   - 특정 카메라 이름(예: `--camera "정우방"`) 또는 콤마로 구분된 여러 카메라(`--camera "정우방,정우"`)를 지정하여 다운로드 및 병합할 수 있습니다.
7. **강력한 오류 복구 및 호환성**
   - **암호화 방식 자동 감지**: `AES-128-CBC` 암호화 영상 자동 복호화 + `encryptionMethod: "NONE"` 비암호화 영상 자동 처리.
   - **토큰 만료 정밀 감지**: Tapo Care `code: 15000` 및 HTTP 401 오류를 감지하여 명확한 재로그인 및 이어받기 안내 제공.
   - **네트워크 재시도 (Retry)**: 일시적 네트워크 순단 시 최대 3회 자동 재시도.
   - **개별 오류 격리**: 특정 파일 다운로드 실패 시 전체 프로세스가 중단되지 않고 다음 파일로 계속 진행.
8. **Windows 완벽 호환 및 간편 실행기**
   - Windows 파일/폴더 금지 문자(`\ / : * ? " < > |`, 제어문자, 예약장치명) 자동 정제.
   - Windows 콘솔 한글 깨짐 방지 UTF-8 자동 설정.
   - 가상환경 자동 감지 런처(`tapo.bat`, `tapo-cli.bat`, `tapo.ps1`).
   - Windows 작업 스케줄러 등록용 원클릭 배치 파일(`backup-windows.bat`).

---

## 🛠️ 설치 및 준비

### 1. 요구 사항
- **Python**: 3.7 이상
- **ffmpeg** *(비디오 병합 `merge-videos` 시 필수)*:
  - Windows: `scoop install ffmpeg` 또는 `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

### 2. 설치

#### Windows (PowerShell 또는 CMD)
```powershell
# 저장소 복제 및 이동
git clone https://github.com/hee10k/tapo-cli.git
cd tapo-cli

# 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\Activate.ps1   # CMD의 경우: venv\Scripts\activate.bat

# 필수 패키지 설치
pip install -r requirements.txt

# (선택 사항) 시스템 전역/가상환경 내에서 'tapo' 명령어로 실행할 수 있도록 등록
pip install -e .
```

#### Linux / macOS
```bash
git clone https://github.com/hee10k/tapo-cli.git
cd tapo-cli

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
chmod +x tapo-cli.py
```

---

## 💻 명령어 상세 사용법

실행 시 `tapo`, `.\tapo.bat` (Windows), 또는 `python tapo-cli.py` 중 편한 방식을 사용하실 수 있습니다.

### 1. 로그인 (`login`)
TP-Link Tapo 클라우드 계정으로 인증합니다.
```powershell
tapo login
```
- 아이디(이메일)와 비밀번호를 입력합니다.
- MFA 푸시 알림이 앱으로 오지 않는 경우, **이메일 인증 코드 수신 옵션(`--mfa-type 2`)**을 사용하세요:
  ```powershell
  tapo login --mfa-type 2
  ```

---

### 2. 비디오 보관 현황 및 기록 조회

#### 카메라별 보관 현황 한눈에 요약 확인 (`check_video_history.py`)
현재 Tapo Cloud에 보관된 비디오 수, 30일 롤링 보관 기간, 가장 오래된 영상 시점과 최신 시점을 조회합니다:
```powershell
python check_video_history.py
```
*출력 예시:*
```text
======================================================================
 [카메라별 비디오 다운로드 가능 기간 및 현황]
======================================================================
▶ 카메라: '정우방' (기기 ID: 8021D1615A5F4F65142D082E14F91E1224BD6D7A)
  • 다운로드 가능한 총 비디오 수 : 12,165개
  • 다운로드 가능 시작 시점 (가장 오래된 비디오) : 2026-08-07 00:00:56
  • 최근 비디오 시점 : 2026-09-05 23:20:31
  • 실제 보관 일수 범위 : 약 30일간의 영상 보관 중
======================================================================
```

#### 비디오 목록 조회 (`list-videos`)
지정한 기간(일수) 동안의 비디오 목록을 확인합니다:
```powershell
tapo list-videos --days 30 --camera "정우방"
```

---

### 3. 비디오 대량 고속 다운로드 (`download-videos`)

가장 오래된 날짜부터 순차 스트리밍하며, 기본 8스레드 병렬로 초고속 다운로드합니다.

```powershell
# 특정 카메라(예: "정우방")의 최근 60일치 영상을 C:\TapoBackups에 8스레드 병렬 다운로드
tapo download-videos --camera "정우방" --days 60 --path "C:\TapoBackups"

# 동시 다운로드 스레드 수 변경 (예: 초고속 16스레드)
tapo download-videos --camera "정우방" --days 60 --path "C:\TapoBackups" --concurrency 16

# 여러 대의 카메라 동시 지정 (쉼표로 구분)
tapo download-videos --camera "정우방,정우" --days 30 --path "C:\TapoBackups"

# 모든 카메라 다운로드
tapo download-videos --days 30 --path "C:\TapoBackups"

# 기존 파일을 덮어쓰며 강제 재다운로드할 때
tapo download-videos --camera "정우방" --overwrite 1 --path "C:\TapoBackups"
```

**실시간 콘솔 출력 화면 예시:**
```text
Found 1 camera(s):
- 정우방 (8021D1615A5F4F65142D082E14F91E1224BD6D7A)

================================================================================
 ▶ 카메라: '정우방' (동시 다운로드 스레드: 8개)
================================================================================
  [ 4262/12,165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:30:28 -> [건너뜀] 이미 존재함 (1.5 MB)
  [ 4263/12,165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:31:10 -> [다운로드 완료] (2.4 MB)
  [ 4264/12,165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:32:05 -> [다운로드 완료] (1.8 MB)
  [ 4265/12,165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:34:40 -> [다운로드 완료] (3.1 MB)
```

#### `download-videos` 옵션 안내
| 옵션 | 단축키 | 설명 | 기본값 |
|---|---|---|---|
| `--camera` | `-c` | 대상 카메라 이름(별칭) 또는 기기 ID (콤마로 여러 개 가능, "all"은 전체) | 전체 카메라 |
| `--days` | `-d` | 과거 며칠 전까지의 영상을 다운로드할지 지정 | `1` (또는 지정값) |
| `--path` | `-p` | 영상이 저장될 기본 디렉터리 경로 | 사용자 홈 (`~/`) |
| `--concurrency` | `-w` | 동시 병렬 다운로드 스레드 개수 | `8` |
| `--overwrite` | `-o` | `0`: 기존 정상 파일 스킵, `1`: 기존 파일 덮어쓰기 | `0` |

---

### 4. 연속 CCTV 비디오 무손실 이어붙이기 (`merge-videos`)

CCTV 모션 감지로 인해 수십 초 ~ 수 분 단위로 잘게 쪼개진 비디오들을 하나의 긴 영상으로 병합합니다. 앞선 영상의 종료 시각과 다음 영상의 시작 시각 차이가 **설정값(기본 60초) 이하**일 때 자동으로 연속된 클립으로 묶어 병합합니다.

```powershell
# 기본 실행: 60초 이하 간격 연속 영상 자동 무손실 병합
tapo merge-videos --path "C:\TapoBackups" --camera "정우방"

# 연속 판별 간격 변경 (예: 120초 이하 간격까지 모두 하나로 이어붙임)
tapo merge-videos --path "C:\TapoBackups" --camera "정우방" --max-gap 120

# 병합 완료 후 원본 조각 파일 자동 삭제 (공간 절약)
tapo merge-videos --path "C:\TapoBackups" --camera "정우방" --delete-source

# 병합 결과 파일 저장 폴더를 별도로 지정할 때
tapo merge-videos --path "C:\TapoBackups" --camera "정우방" --output-dir "D:\MergedVideos"
```

- **저장 위치 및 파일명**: 기본적으로 `<카메라폴더>/merged/<날짜>/` 경로에 저장되며, 시작~종료 시각과 클립 수, 총 재생 시간이 파일명에 자동으로 기록됩니다:
  `2026-08-17 13-30-28_to_13-45-10 (6clips, 14m42s).mp4`
- **초고속 무손실**: `ffmpeg`의 stream copy(`-c copy`) 방식을 사용하여 화질 손실이나 인코딩 렉 없이 수 초 만에 병합됩니다.
- **스마트 스킵**: 이미 병합된 파일이 존재하면 중복 작업을 건너뜁니다.

#### `merge-videos` 옵션 안내
| 옵션 | 단축키 | 설명 | 기본값 |
|---|---|---|---|
| `--path` | | 비디오가 저장된 기본 디렉터리 경로 | 사용자 홈 (`~/`) |
| `--camera` | `-c` | 특정 카메라 폴더 필터링 | 전체 카메라 폴더 |
| `--max-gap` | | 연속된 클립으로 판단할 앞뒤 영상 간 최대 시간 간격(초) | **`60`** |
| `--output-dir` | | 병합된 파일이 저장될 커스텀 디렉터리 경로 | `<카메라폴더>/merged` |
| `--delete-source` | | 병합 완료 후 원본 조각 파일 자동 삭제 여부 | `False` (원본 보존) |

---

## ⏰ 백업 자동화 (일일 스케줄러)

### Windows (작업 스케줄러 - Task Scheduler)
네이티브 배치 스크립트 [backup-windows.bat](file:///C:/Users/aigo90/projects/tapo-cli/backup-windows.bat)가 기본 포함되어 있습니다:
1. `backup-windows.bat` 파일을 열고 원하는 설정을 확인/수정합니다:
   - `BACKUP_DIR`: 저장 폴더 (기본: `%USERPROFILE%\TapoBackups`)
   - `DAYS`: 보관일수 (기본: `7`)
   - `CAMERA`: 특정 카메라 지정 (예: `정우방`)
   - `CONCURRENCY`: 동시 다운로드 스레드 수 (기본: `8`)
2. **시작 메뉴**에서 **작업 스케줄러**(`taskschd.msc`)를 실행합니다.
3. **기본 작업 만들기...** 클릭:
   - **이름**: `Tapo Daily Backup`
   - **트리거**: 매일(Daily), 원하는 시각(예: 새벽 04:00)
   - **동작**: 프로그램 시작
   - **프로그램/스크립트**: `C:\Users\aigo90\projects\tapo-cli\backup-windows.bat`
   - **시작 위치(옵션)**: `C:\Users\aigo90\projects\tapo-cli`

### Linux / macOS (Cron)
```bash
crontab -e
```
매일 새벽 4시 30분에 자동 백업 등록 예시:
```cron
30 4 * * * /home/<user>/tapo-cli/venv/bin/python /home/<user>/tapo-cli/tapo-cli.py download-videos --days 7 --path /home/<user>/TapoBackups --camera "정우방" --concurrency 8
```

---

## ❓ 자주 묻는 질문 및 문제 해결 (FAQ)

- **Q. 다운로드가 중간에 멈추거나 토큰이 만료되었다고 나옵니다 (`Token expired` / `code: 15000`)**
  - Tapo의 보안 정책상 세션 토큰은 일정 시간 후 만료됩니다.
  - `tapo login` (또는 `.\tapo.bat login`)을 실행해 다시 로그인한 뒤 다운로드 명령을 재실행하시면 됩니다.
  - 이미 받아둔 파일은 **스마트 중복 제거 기능으로 순식간에 자동 건너뛰므로** 이전에 멈춘 위치부터 곧바로 이어서 다운로드됩니다.
- **Q. `[오류] 지원되지 않는 암호화 방식: NONE` 오류가 났었습니다**
  - 최신 버전에서 비암호화 영상(`NONE`)도 자동 감지하여 원본 그대로 정상 저장되도록 패치 완료되었습니다.
- **Q. 특정 파일 다운로드 도중 네트워크가 끊기면 전체 작업이 죽나요?**
  - 개별 비디오 다운로드 실패 시 해당 파일만 경고 로그를 남기고, 전체 프로세스는 중단 없이 다음 비디오를 계속 다운로드하도록 설계되어 있습니다.

---
---

<a name="english-guide"></a>
# 🌐 English Guide

`tapo-cli` is a cross-platform command-line tool designed to batch-download and losslessly merge video recordings from your Tapo TP-Link Cloud account.

Supports **Windows**, **Linux**, and **macOS** with native path resolution, character sanitization, UTF-8 console output, parallel streaming downloads, and fast lossless clip merging.

---

## Key Features

- **High-Speed Parallel Downloads**: Download multiple videos simultaneously using multithreading (`--concurrency 8` / `-w 8` by default) for 5x~10x faster backups.
- **Sequential Oldest-First Streaming**: Downloads start immediately with the oldest recorded video without waiting to fetch the entire remote catalog.
- **Instant Pre-Check Deduplication**: Fast local pre-checks skip already downloaded files in seconds before worker submission, with automatic re-downloading of corrupted 0-byte files.
- **Lossless CCTV Clip Merging (`merge-videos`)**: Combines fragmented motion-detection clips into continuous long videos using ffmpeg (`-c copy`) when the gap between recordings is within a configurable threshold (**default: 60 seconds**).
- **Encryption & Non-Encryption Support**: Automatic AES-128-CBC decryption and seamless handling of unencrypted (`NONE`) recordings.
- **Robust Error Handling**: Precise detection of Tapo Care token expiration (`code: 15000`), 3x automatic retries on transient network errors, and non-fatal per-file error isolation.
- **Windows-First Compatibility**: Safe path sanitization (`\ / : * ? " < > |`), UTF-8 console output, and native `.bat` / `.ps1` launchers.
- **Daily Automated Backups**: Native Windows Task Scheduler script (`backup-windows.bat`) and Linux cron examples.

---

## Installation & Quick Start

### 1. Requirements
- **Python**: 3.7+
- **ffmpeg** *(Required for `merge-videos`)*:
  - Windows: `scoop install ffmpeg` or `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

### 2. Setup

#### Windows (PowerShell or CMD)
```powershell
git clone https://github.com/hee10k/tapo-cli.git
cd tapo-cli

python -m venv venv
.\venv\Scripts\Activate.ps1   # In CMD: venv\Scripts\activate.bat
pip install -r requirements.txt
pip install -e .
```

#### Linux / macOS
```bash
git clone https://github.com/hee10k/tapo-cli.git
cd tapo-cli

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
chmod +x tapo-cli.py
```

---

## Command Reference

### 1. Login
```powershell
tapo login
# If MFA push notification does not arrive, use email verification:
tapo login --mfa-type 2
```

### 2. Inspect Cloud Videos
```powershell
# Summary of cloud retention, earliest/latest dates, and total counts
python check_video_history.py

# Query video list
tapo list-videos --days 30 --camera "정우방"
```

### 3. Download Videos (`download-videos`)
```powershell
# Download with 8 parallel threads (default)
tapo download-videos --camera "정우방" --days 60 --path "C:\TapoBackups"

# High-speed download with 16 threads
tapo download-videos --camera "정우방" --days 60 --path "C:\TapoBackups" --concurrency 16

# Download multiple cameras
tapo download-videos --camera "Cam1,Cam2" --days 30 --path "C:\TapoBackups"
```

| Option | Short | Description | Default |
|---|---|---|---|
| `--camera` | `-c` | Camera alias or device ID filter (comma-separated or "all") | All cameras |
| `--days` | `-d` | Number of past days to download | `1` |
| `--path` | `-p` | Destination directory | `~/` |
| `--concurrency` | `-w` | Number of concurrent download worker threads | `8` |
| `--overwrite` | `-o` | `0` = skip existing files, `1` = force re-download | `0` |

### 4. Merge Continuous Clips (`merge-videos`)
```powershell
# Merge clips where gap is <= 60 seconds (default)
tapo merge-videos --path "C:\TapoBackups" --camera "정우방"

# Custom continuity threshold (e.g. 120 seconds)
tapo merge-videos --path "C:\TapoBackups" --camera "정우방" --max-gap 120

# Delete fragmented source clips after merge
tapo merge-videos --path "C:\TapoBackups" --camera "정우방" --delete-source
```

| Option | Short | Description | Default |
|---|---|---|---|
| `--path` | | Directory containing camera backup folders | `~/` |
| `--camera` | `-c` | Specific camera folder name to process | All camera folders |
| `--max-gap` | | Maximum gap in seconds between continuous clips | `60` |
| `--output-dir` | | Custom directory for merged files | `<camera_dir>/merged` |
| `--delete-source` | | Delete fragmented source files after merge | `False` |

---

## Running Unit Tests
```powershell
python -m unittest discover tests
```

---

## License & Disclaimer
This project is an unofficial community tool and is not affiliated with or endorsed by TP-Link or Tapo.
