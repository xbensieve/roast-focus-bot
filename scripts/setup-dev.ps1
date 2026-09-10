$ErrorActionPreference = 'Stop'

Write-Host 'Creating virtual environment...'
if (Get-Command 'py' -ErrorAction SilentlyContinue) {
    try {
        & py -3.12 -m venv .venv
    } catch {
        & py -3 -m venv .venv
    }
} else {
    & python -m venv .venv
}
Write-Host 'Installing dependencies...'
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Write-Host 'Development environment ready.'
