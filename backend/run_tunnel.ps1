$ErrorActionPreference = 'Stop'

$backendDir = $PSScriptRoot
$projectRoot = Split-Path -Parent $backendDir
$pythonCandidates = @(
    Join-Path $backendDir 'venv\Scripts\python.exe'
    Join-Path $projectRoot '.venv\Scripts\python.exe'
)
$python = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$publicHostname = ''
if ($env:PUBLIC_HOSTNAME) {
    $publicHostname = $env:PUBLIC_HOSTNAME.Trim()
}

$tunnelName = ''
if ($env:CLOUDFLARED_TUNNEL_NAME) {
    $tunnelName = $env:CLOUDFLARED_TUNNEL_NAME.Trim()
}

if (-not $python) {
    throw 'Python virtual environment not found. Expected backend\venv or .venv at the project root.'
}

if (-not (Test-Path $cloudflared)) {
    throw "cloudflared not found at $cloudflared"
}

Write-Host 'Starting Django on http://127.0.0.1:8000 if it is not already running...' -ForegroundColor Cyan

try {
    $listener = [System.Net.Sockets.TcpClient]::new()
    $listener.Connect('127.0.0.1', 8000)
    $listener.Close()
    $serverAlreadyRunning = $true
} catch {
    $serverAlreadyRunning = $false
}

if (-not $serverAlreadyRunning) {
    Start-Process -FilePath $python -ArgumentList @('manage.py', 'runserver', '127.0.0.1:8000') -WorkingDirectory $backendDir -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
}

$cloudflaredArgs = @('tunnel')

if ($tunnelName) {
    $cloudflaredArgs += @('--name', $tunnelName)
}

if ($publicHostname) {
    $cloudflaredArgs += @('--hostname', $publicHostname)
    Write-Host "Using stable hostname: $publicHostname" -ForegroundColor Green
} else {
    Write-Host 'No PUBLIC_HOSTNAME set, so cloudflared will create a temporary trycloudflare URL.' -ForegroundColor Yellow
}

$cloudflaredArgs += @('--url', 'http://127.0.0.1:8000')

Write-Host 'Starting cloudflared tunnel...' -ForegroundColor Cyan
Start-Process -FilePath $cloudflared -ArgumentList $cloudflaredArgs -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru | Out-Null

Write-Host ''
Write-Host 'If you set PUBLIC_HOSTNAME and CLOUDFLARED_TUNNEL_NAME, that hostname should stay stable between restarts.' -ForegroundColor Green
Write-Host 'If you left them blank, the tunnel will still work, but the URL may change each time cloudflared restarts.' -ForegroundColor Yellow
