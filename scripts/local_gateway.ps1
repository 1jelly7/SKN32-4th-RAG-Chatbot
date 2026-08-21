param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$NginxConfig = "deploy/nginx/local.conf"
$RuntimeDirectory = Join-Path $ProjectRoot "temp"
$LogDirectory = Join-Path $ProjectRoot "logs"
$StatePath = Join-Path $RuntimeDirectory "local-gateway-services.json"
$NginxPidPath = Join-Path $RuntimeDirectory "nginx-local.pid"
$NginxPathState = Join-Path $RuntimeDirectory "nginx-local.exe.path"
$NginxPrefix = $ProjectRoot.Replace("\", "/") + "/"

function Get-NginxPath {
    $command = Get-Command nginx -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    if (Test-Path -LiteralPath $NginxPathState) {
        $savedPath = (Get-Content -Raw -LiteralPath $NginxPathState).Trim()
        if (Test-Path -LiteralPath $savedPath) {
            return $savedPath
        }
    }
    throw "nginx was not found. Install nginx and add it to PATH as described in README.md."
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit=$LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Test-TrackedProcess {
    param([pscustomobject]$Record)

    $process = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }

    $expectedStart = [DateTime]::Parse(
        [string]$Record.started_at,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind
    )
    return [Math]::Abs(($process.StartTime.ToUniversalTime() - $expectedStart).TotalSeconds) -lt 1
}

function Stop-TrackedProcess {
    param([pscustomobject]$Record)

    if (Test-TrackedProcess $Record) {
        Stop-Process -Id ([int]$Record.pid)
        Write-Host "$($Record.name) stopped: PID $($Record.pid)"
    }
}

function Read-State {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return @()
    }
    $state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
    return @($state)
}

function Test-NginxProcess {
    if (-not (Test-Path -LiteralPath $NginxPidPath)) {
        return $false
    }
    try {
        $nginxPid = [int](Get-Content -Raw -LiteralPath $NginxPidPath).Trim()
        $process = Get-Process -Id $nginxPid -ErrorAction SilentlyContinue
        return $null -ne $process -and $process.ProcessName -eq "nginx"
    } catch {
        return $false
    }
}

function Stop-LocalGateway {
    try {
        $nginx = Get-NginxPath
    } catch {
        $nginx = $null
    }
    if ($null -ne $nginx -and (Test-NginxProcess)) {
        & $nginx -p $NginxPrefix -c $NginxConfig -s quit
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Nginx gateway graceful shutdown requested."
        } else {
            Write-Warning "Nginx graceful shutdown failed. Check logs/nginx-local-error.log."
        }
    } elseif (Test-NginxProcess) {
        Write-Warning "Nginx is running, but the nginx command is unavailable. It was not stopped."
    } else {
        Remove-Item -LiteralPath $NginxPidPath -Force -ErrorAction SilentlyContinue
    }

    foreach ($record in (Read-State)) {
        Stop-TrackedProcess $record
    }
    Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
}

function Start-LocalGateway {
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        throw ".venv Python was not found: $PythonPath"
    }
    $nginx = Get-NginxPath

    New-Item -ItemType Directory -Force -Path $RuntimeDirectory, $LogDirectory | Out-Null
    Set-Content -LiteralPath $NginxPathState -Value $nginx -Encoding ascii

    $active = @(Read-State | Where-Object { Test-TrackedProcess $_ })
    if (-not (Test-NginxProcess)) {
        Remove-Item -LiteralPath $NginxPidPath -Force -ErrorAction SilentlyContinue
    }
    if ($active.Count -gt 0 -or (Test-NginxProcess)) {
        throw "The local gateway is already running or has stale state. Run status or stop first."
    }

    Push-Location $ProjectRoot
    $started = @()
    try {
        Invoke-Checked $PythonPath @("django_app/manage.py", "check")
        Invoke-Checked $PythonPath @("django_app/manage.py", "collectstatic", "--clear", "--noinput")
        Invoke-Checked $nginx @("-p", $NginxPrefix, "-t", "-c", $NginxConfig)

        $djangoArguments = @{
            FilePath = $PythonPath
            ArgumentList = @("django_app/manage.py", "runserver", "127.0.0.1:8001", "--noreload")
            WorkingDirectory = $ProjectRoot
            WindowStyle = "Hidden"
            RedirectStandardOutput = Join-Path $LogDirectory "django-local.out.log"
            RedirectStandardError = Join-Path $LogDirectory "django-local.error.log"
            PassThru = $true
        }
        $django = Start-Process @djangoArguments
        $started += [pscustomobject]@{
            name = "Django"
            pid = $django.Id
            started_at = $django.StartTime.ToUniversalTime().ToString("o")
        }

        $fastapiArguments = @{
            FilePath = $PythonPath
            ArgumentList = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002")
            WorkingDirectory = $ProjectRoot
            WindowStyle = "Hidden"
            RedirectStandardOutput = Join-Path $LogDirectory "fastapi-local.out.log"
            RedirectStandardError = Join-Path $LogDirectory "fastapi-local.error.log"
            PassThru = $true
        }
        $fastapi = Start-Process @fastapiArguments
        $started += [pscustomobject]@{
            name = "FastAPI"
            pid = $fastapi.Id
            started_at = $fastapi.StartTime.ToUniversalTime().ToString("o")
        }

        $started | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8
        Invoke-Checked $nginx @("-p", $NginxPrefix, "-c", $NginxConfig)

        Write-Host "Local project started: http://127.0.0.1:8000/"
        Write-Host "Status: .\scripts\local_gateway.ps1 status"
        Write-Host "Stop: .\scripts\local_gateway.ps1 stop"
    } catch {
        foreach ($record in $started) {
            Stop-TrackedProcess $record
        }
        Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
        throw
    } finally {
        Pop-Location
    }
}

function Show-LocalGatewayStatus {
    $records = @(Read-State)
    if ($records.Count -eq 0) {
        Write-Host "Django/FastAPI: stopped"
    } else {
        foreach ($record in $records) {
            $status = if (Test-TrackedProcess $record) { "running" } else { "stopped" }
            Write-Host "$($record.name): $status (PID $($record.pid))"
        }
    }

    if (Test-NginxProcess) {
        $nginxPid = (Get-Content -Raw -LiteralPath $NginxPidPath).Trim()
        Write-Host "Nginx: running (PID $nginxPid)"
    } else {
        Write-Host "Nginx: stopped"
    }
}

switch ($Action) {
    "start" { Start-LocalGateway }
    "stop" { Stop-LocalGateway }
    "restart" {
        Stop-LocalGateway
        Start-LocalGateway
    }
    "status" { Show-LocalGatewayStatus }
}
