# tapo-cli: Tapo TP-Link Cloud Video Downloader & Merger

`tapo-cli` is a command-line tool designed to batch-download and manage continuous video recordings from your Tapo TP-Link Cloud account.

Supports **Windows**, **Linux**, and **macOS** with native path resolution, character sanitization, UTF-8 console output, and fast lossless video merging.

---

## Key Features

- **Sequential Oldest-First Streaming**: Downloads start immediately with the oldest recorded video without waiting to fetch the entire catalog.
- **High-Speed Parallel Downloads**: Download multiple videos concurrently with multithreading (`--concurrency 8` / `-w 8` by default) to dramatically accelerate bulk backups (5x~10x faster).
- **Camera Selection & Filtering**: Target one or more specific cameras (`--camera "정우방"` or `--camera "Cam1,Cam2"`).
- **Real-Time Progress Display**: View ongoing progress with `[current/total] (progress%) [D-day] [timestamp] [filesize] -> filename`.
- **Smart Deduplication**: Automatically skips already downloaded files and repairs corrupted/empty (0-byte) downloads.
- **Continuous CCTV Clip Merging (`merge-videos`)**: Losslessly combines fragmented motion-detection clips into continuous long videos using ffmpeg (`-c copy`) when the gap between recordings is within a configurable threshold (**default: 60 seconds**).
- **Windows-First Compatibility**: Automatic sanitization of invalid path characters (`\ / : * ? " < > |`), UTF-8 console output, and native `.bat` / `.ps1` wrappers.
- **Daily Automated Backups**: Ready-to-use Windows Task Scheduler batch script (`backup-windows.bat`) and Linux cron examples.

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
# Clone the repository
git clone https://github.com/hee10k/tapo-cli.git
cd tapo-cli

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # In CMD: venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# (Optional) Install tapo CLI command globally within the environment
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

## Usage Guide

You can run commands using `tapo`, `.\tapo.bat` (Windows), or `python tapo-cli.py`.

### 1. Login
```powershell
tapo login
```
Prompts for your TP-Link account credentials. If MFA push notifications do not arrive, select email verification:
```powershell
tapo login --mfa-type 2
```

---

### 2. Inspect Available Cloud Videos
Check retention dates, total video count, and earliest/latest recording times across all cameras:
```powershell
python check_video_history.py
```
Or list videos in JSON format:
```powershell
tapo list-videos --days 30
```

---

### 3. Download Videos (`download-videos`)

Downloads start from the **oldest video first** and stream sequentially with live progress:

```powershell
# High-speed parallel download with 8 threads (default)
tapo download-videos --camera "정우방" --days 60 --path "C:\TapoBackups"

# Custom concurrency (e.g. 16 threads for ultra-fast downloads)
tapo download-videos --camera "정우방" --days 60 --path "C:\TapoBackups" --concurrency 16

# Download from multiple cameras (comma-separated)
tapo download-videos --camera "정우방,정우" --days 30 --path "C:\TapoBackups"

# Download all cameras
tapo download-videos --days 30 --path "C:\TapoBackups"
```

**Real-Time Console Output Example:**
```text
Found 1 camera(s):
- 정우방 (xxxxxxxx)

[1/1] Processing camera: 정우방 (xxxxxxxx)
======================================================================
  [ 4262/12165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:30:28 -> [건너뜀] 이미 존재함 (1.5 MB)
  [ 4263/12165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:31:10 -> [다운로드 완료] (2.4 MB)
  [ 4264/12165] ( 35.0%) [19일 전 (D-19)] 2026-08-17 13:32:05 -> [다운로드 완료] (1.8 MB)
======================================================================
```

#### Download Options
| Option | Short | Description | Default |
|---|---|---|---|
| `--camera` | `-c` | Camera alias/name filter (exact or comma-separated list) | All cameras |
| `--days` | `-d` | Number of past days to query | `7` |
| `--path` | `-p` | Destination directory | User home (`~/`) |
| `--overwrite` | `-o` | `0` = skip existing valid files, `1` = force re-download | `0` |
| `--concurrency` | `-w` | Number of parallel download worker threads | `8` |

---

### 4. Merge Continuous Clips (`merge-videos`)

CCTV motion alerts often slice a single event into multiple 1~3 minute files. `merge-videos` connects clips whose gap is less than or equal to `--max-gap` seconds without re-encoding (lossless `-c copy` via ffmpeg).

```powershell
# Merge clips with the default 60-second continuity threshold
tapo merge-videos --path "C:\TapoBackups" --camera "정우방"

# Merge clips with a custom threshold (e.g., 120 seconds)
tapo merge-videos --path "C:\TapoBackups" --max-gap 120

# Automatically delete fragmented source clips after successful merge
tapo merge-videos --path "C:\TapoBackups" --camera "정우방" --delete-source
```

- **Output naming**: Files are saved in `<camera_dir>/merged/` as `YYYY-MM-DD_HH-MM-SS_to_HH-MM-SS.mp4`.
- **Lossless & Fast**: Processes gigabytes of footage in seconds without CPU-heavy transcoding.

#### Merge Options
| Option | Short | Description | Default |
|---|---|---|---|
| `--path` | | Directory containing downloaded camera folders | User home (`~/`) |
| `--camera` | `-c` | Specific camera folder name to process | All camera folders |
| `--max-gap` | | Maximum gap in seconds between clips to treat as continuous | `60` |
| `--output-dir` | | Custom directory for merged files | `<camera_dir>/merged` |
| `--delete-source` | | Delete fragmented source files after a successful merge | `False` |

---

## Automated Backups

### Windows (Task Scheduler)
Use the included `backup-windows.bat` script:
1. Edit variables inside [backup-windows.bat](file:///C:/Users/aigo90/projects/tapo-cli/backup-windows.bat) (`BACKUP_DIR`, `DAYS`, `CAMERA`).
2. Open **Task Scheduler** (`taskschd.msc`).
3. Click **Create Basic Task...**:
   - **Trigger**: Daily at your preferred time (e.g., 04:00 AM)
   - **Action**: Start a program
   - **Program/script**: `C:\path\to\tapo-cli\backup-windows.bat`
   - **Start in**: `C:\path\to\tapo-cli`

### Linux / macOS (Cron)
```bash
crontab -e
```
Add the daily entry:
```cron
30 4 * * * /home/<user>/tapo-cli/venv/bin/python /home/<user>/tapo-cli/tapo-cli.py download-videos --days 7 --path /home/<user>/TapoBackups --overwrite 0
```

---

## Running Tests

Run the full test suite with Python's built-in `unittest`:
```powershell
python -m unittest discover tests
```
All test suites verify Windows path sanitization, deduplication logic, camera filtering, and the ffmpeg video merging pipeline.

---

## License & Disclaimer
This project is an unofficial community tool and is not affiliated with or endorsed by TP-Link or Tapo.
