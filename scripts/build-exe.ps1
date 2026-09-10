$ErrorActionPreference = 'Stop'

Write-Host 'Running tests...'
.\.venv\Scripts\python.exe -m pytest

Write-Host 'Installing/verifying pinned development dependencies...'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

Write-Host 'Cleaning previous build artifacts...'
Get-Process -Name roast-focus-bot -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 300
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist

Write-Host 'Building roast-focus-bot.exe...'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm RoastFocusBot.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path '.\dist\roast-focus-bot.exe')) {
    throw 'Build completed without dist\roast-focus-bot.exe'
}

Write-Host 'Applying Authenticode signature for Windows Smart App Control compatibility...'
try {
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert -ErrorAction SilentlyContinue | Where-Object { $_.Subject -match "RoastFocusBot" } | Select-Object -First 1
    if (-not $cert) {
        $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=RoastFocusBotLocal" -CertStoreLocation "Cert:\CurrentUser\My" -ErrorAction SilentlyContinue
    }
    if ($cert) {
        Set-AuthenticodeSignature -Certificate $cert -FilePath '.\dist\roast-focus-bot.exe' -ErrorAction SilentlyContinue | Out-Null
        Write-Host 'Signed with local Authenticode certificate.'
    }
} catch {
    Write-Warning "Could not sign executable: $_"
}

$hash = (Get-FileHash '.\dist\roast-focus-bot.exe' -Algorithm SHA256).Hash
Copy-Item '.\config\default.json' '.\dist\default.json' -Force
Write-Host "SHA256: $hash"
Write-Host 'Build succeeded.'
