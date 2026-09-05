param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path (Join-Path $scriptDir "venv\Scripts\python.exe")) {
    $pythonExe = Join-Path $scriptDir "venv\Scripts\python.exe"
} elseif (Test-Path (Join-Path $scriptDir ".venv\Scripts\python.exe")) {
    $pythonExe = Join-Path $scriptDir ".venv\Scripts\python.exe"
} else {
    $pythonExe = "python"
}

& $pythonExe (Join-Path $scriptDir "tapo-cli.py") @ScriptArgs
