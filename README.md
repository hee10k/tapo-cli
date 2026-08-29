# tapo-cli: Tapo TP-Link Cloud Video Downloader

tapo-cli is a command-line utility designed to streamline the process of batch-downloading your videos from the Tapo TP-Link Cloud.

Please note that this utility has not been tested on Windows systems. It is recommended to utilize the [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/install) for Windows users.

The utility is compatible with any Debian-based operating system that has `python3` and `pip3` installed.

## Usage Instructions
To begin using Tapo-CLI, follow these steps:

```
git clone https://github.com/dimme/tapo-cli.git
cd tapo-cli
python3 -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt
chmod +x tapo-cli.py
./tapo-cli.py login
./tapo-cli.py list-videos
./tapo-cli.py download-videos
```

Recent distributions (Ubuntu 24.04+, Debian 12+, Fedora) refuse `pip3 install` outside a
virtual environment, so the `venv` steps above are required rather than optional. Remember to
run `. venv/bin/activate` in any new shell before using the tool, or call it through the venv
directly with `/path/to/tapo-cli/venv/bin/python /path/to/tapo-cli/tapo-cli.py`, which is the
form to use in cron jobs and scheduled tasks.

For additional information and options, please refer to `./tapo-cli.py --help` and `./tapo-cli.py [COMMAND] --help`.

## Troubleshooting

**`Token expired` (error `-20651`)** — access tokens are short-lived. Run `./tapo-cli.py login` again.

## Automating Backups

### Windows

To automate daily backups on Windows, create a `.bat` file with the following content and schedule it to run once per day using Task Scheduler:

```
ubuntu.exe run "/home/<user>/tapo-cli/venv/bin/python /home/<user>/tapo-cli/tapo-cli.py download-videos --days 7 --path /mnt/c/TapoBackups --overwrite 0"
```

This process requires the [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/install). You may also choose to schedule the task to run upon system logon.

### Linux

To automate daily backups on Linux, create a cron task by executing:

```
sudo crontab -e
```

Then, append a line similar to the one below, adjusted to match your specific paths:

```
30 4 * * *  <user> /home/<user>/tapo-cli/venv/bin/python /home/<user>/tapo-cli/tapo-cli.py download-videos --days 7 --path /home/<user>/TapoBackups --overwrite 0
```

This will schedule the task to run at 4:30 AM every day.
