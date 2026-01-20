param(
  [Parameter(Mandatory = $false)]
  [ValidateSet("start", "stop", "restart", "status", "logs", "install-deps")]
  [string]$Action = "start",

  [Parameter(Mandatory = $false)]
  [string]$HostAddress = "0.0.0.0",

  [Parameter(Mandatory = $false)]
  [int]$Port = 19999,

  [Parameter(Mandatory = $false)]
  [string]$SecretKey = "",

  [Parameter(Mandatory = $false)]
  [string]$PasswordMap = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $ProjectRoot "run"
$LogsDir = Join-Path $ProjectRoot "logs"
$PidFile = Join-Path $RunDir "weblog.pid"
$StdoutLog = Join-Path $LogsDir "weblog.stdout.log"
$StderrLog = Join-Path $LogsDir "weblog.stderr.log"

$pythonFilePath = $null
$pythonBaseArgs = @()

if (($null -ne $env:VIRTUAL_ENV) -and ($env:VIRTUAL_ENV -ne "")) {
  $activeVenvPython = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
  if (Test-Path -LiteralPath $activeVenvPython) {
    $pythonFilePath = $activeVenvPython
  }
}

if ($null -eq $pythonFilePath) {
  $localVenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $localVenvPython) {
    $pythonFilePath = $localVenvPython
  }
}

if ($null -eq $pythonFilePath) {
  $python = Get-Command "python" -ErrorAction SilentlyContinue
  if ($null -ne $python) {
    $pythonFilePath = $python.Source
  }
}

if ($null -eq $pythonFilePath) {
  $py = Get-Command "py" -ErrorAction SilentlyContinue
  if ($null -ne $py) {
    $pythonFilePath = $py.Source
    $pythonBaseArgs = @("-3")
  }
} else {
  $pythonBaseArgs = @()
}

if ($null -eq $pythonFilePath) {
  throw "Python not found. Install Python 3 or create .venv"
}

if (-not (Test-Path -LiteralPath $RunDir)) { New-Item -ItemType Directory -Path $RunDir | Out-Null }
if (-not (Test-Path -LiteralPath $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }

try {
  & $pythonFilePath @($pythonBaseArgs + @("-V")) | Out-Null
} catch {
  throw "Python launcher found but no usable runtime. Install Python 3 and retry."
}

function Get-ExcludedTcpPortRanges {
  $out = & netsh interface ipv4 show excludedportrange protocol=tcp 2>$null
  $ranges = @()
  foreach ($line in $out) {
    if ($line -match "^\s*(\d+)\s+(\d+)\s*(\*?)\s*$") {
      $ranges += [PSCustomObject]@{
        StartPort = [int]$matches[1]
        EndPort = [int]$matches[2]
      }
    }
  }
  return $ranges
}

function Test-TcpPortExcluded {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][object[]]$Ranges
  )
  foreach ($r in $Ranges) {
    if (($Port -ge $r.StartPort) -and ($Port -le $r.EndPort)) { return $true }
  }
  return $false
}

function Test-TcpPortBindable {
  param(
    [Parameter(Mandatory = $true)][string]$HostAddress,
    [Parameter(Mandatory = $true)][int]$Port
  )
  try {
    $ip = $null
    if ($HostAddress -eq "0.0.0.0") {
      $ip = [System.Net.IPAddress]::Any
    } else {
      $ip = [System.Net.IPAddress]::Parse($HostAddress)
    }
    $listener = [System.Net.Sockets.TcpListener]::new($ip, $Port)
    $listener.Start()
    $listener.Stop()
    return $true
  } catch {
    return $false
  }
}

function Find-UsableTcpPort {
  param(
    [Parameter(Mandatory = $true)][string]$HostAddress,
    [Parameter(Mandatory = $true)][int]$PreferredPort
  )
  $ranges = Get-ExcludedTcpPortRanges
  $candidateList = @($PreferredPort, 19996, 18080, 5000, 8000, 8080, 8888) | Select-Object -Unique
  foreach ($p in $candidateList) {
    if ((-not (Test-TcpPortExcluded -Port $p -Ranges $ranges)) -and (Test-TcpPortBindable -HostAddress $HostAddress -Port $p)) {
      return $p
    }
  }

  for ($p = $PreferredPort + 1; $p -le ($PreferredPort + 500); $p++) {
    if ((-not (Test-TcpPortExcluded -Port $p -Ranges $ranges)) -and (Test-TcpPortBindable -HostAddress $HostAddress -Port $p)) {
      return $p
    }
  }
  return $PreferredPort
}

switch ($Action) {
  "install-deps" {
    & $pythonFilePath @($pythonBaseArgs + @("-m", "pip", "install", "-r", (Join-Path $ProjectRoot "requirements.txt")))
    break
  }

  "status" {
    if (-not (Test-Path -LiteralPath $PidFile)) {
      Write-Output "STOPPED"
      break
    }

    $raw = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not ($raw -match "^\d+$")) {
      Write-Output "STOPPED (pid file corrupted)"
      break
    }

    $processId = [int]$raw
    try {
      $p = Get-Process -Id $processId -ErrorAction Stop
      Write-Output "RUNNING: PID=$($p.Id)"
    } catch {
      Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
      Write-Output "STOPPED (stale pid file cleaned)"
    }
    break
  }

  "stop" {
    if (-not (Test-Path -LiteralPath $PidFile)) {
      Write-Output "STOPPED (no pid file)"
      break
    }

    $raw = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not ($raw -match "^\d+$")) {
      Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
      Write-Output "STOPPED (pid file corrupted, cleaned)"
      break
    }

    $processId = [int]$raw
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
      Write-Output "STOPPED: PID=$processId"
    } catch {
      Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
      Write-Output "STOPPED (stale pid file cleaned)"
    }
    break
  }

  "start" {
    if (Test-Path -LiteralPath $PidFile) {
      $raw = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
      if ($raw -match "^\d+$") {
        $processId = [int]$raw
        try {
          $p = Get-Process -Id $processId -ErrorAction Stop
          Write-Output "ALREADY RUNNING: PID=$($p.Id)"
          break
        } catch {
          Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        }
      } else {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
      }
    }

    $resolvedPort = Find-UsableTcpPort -HostAddress $HostAddress -PreferredPort $Port
    if ($resolvedPort -ne $Port) {
      Write-Output "端口 $Port 无法使用，已自动切换到 $resolvedPort"
      $Port = $resolvedPort
    }

    $env:NOTEPAD_PORT = "$Port"
    $env:NOTEPAD_HOST = "$HostAddress"
    if ($SecretKey -ne "") { $env:FLASK_SECRET_KEY = $SecretKey }
    if ($PasswordMap -ne "") { $env:NOTEPAD_PASSWORD_MAP = $PasswordMap }

    & $pythonFilePath @($pythonBaseArgs + @("-c", "import flask, flask_cors")) | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "Python dependencies missing. Run: .\\weblog-service.ps1 -Action install-deps"
    }

    $pythonCode = "import os; from app import create_production_app; app=create_production_app(); host=os.environ.get('NOTEPAD_HOST','0.0.0.0'); port=int(os.environ.get('NOTEPAD_PORT','19999')); app.run(host=host, port=port, debug=False, threaded=True)"
    $pythonArgLine = @()
    $pythonArgLine += $pythonBaseArgs
    $pythonArgLine += @("-c", ('"{0}"' -f $pythonCode))
    $pythonArgLineString = ($pythonArgLine -join " ")

    $p = Start-Process -FilePath $pythonFilePath -ArgumentList $pythonArgLineString -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog
    Start-Sleep -Milliseconds 500
    try {
      Get-Process -Id $p.Id -ErrorAction Stop | Out-Null
      Set-Content -LiteralPath $PidFile -Value $p.Id -Encoding ASCII
      Write-Output "STARTED: PID=$($p.Id) URL=http://localhost:$Port/"
    } catch {
      if (Test-Path -LiteralPath $StderrLog) {
        $tail = Get-Content -LiteralPath $StderrLog -Tail 30 -ErrorAction SilentlyContinue
        if ($null -ne $tail) { $tail | ForEach-Object { Write-Output $_ } }
      }
      throw "Failed to start. Check logs: $StdoutLog , $StderrLog"
    }
    break
  }

  "restart" {
    & $PSCommandPath -Action stop -HostAddress $HostAddress -Port $Port -SecretKey $SecretKey -PasswordMap $PasswordMap
    & $PSCommandPath -Action start -HostAddress $HostAddress -Port $Port -SecretKey $SecretKey -PasswordMap $PasswordMap
    break
  }

  "logs" {
    if (Test-Path -LiteralPath $StdoutLog) {
      Write-Output "=== STDOUT: $StdoutLog ==="
      Get-Content -LiteralPath $StdoutLog -Tail 200
    } else {
      Write-Output "No STDOUT log: $StdoutLog"
    }

    if (Test-Path -LiteralPath $StderrLog) {
      Write-Output "=== STDERR: $StderrLog ==="
      Get-Content -LiteralPath $StderrLog -Tail 200
    } else {
      Write-Output "No STDERR log: $StderrLog"
    }
    break
  }
}

