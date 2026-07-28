[CmdletBinding()]
param(
    [ValidateSet("serve", "worker")]
    [string] $Mode = "serve",
    [string] $RepoDir = "",
    [int] $Port = 5010,
    [int] $LabAppPort = 5000,
    [string] $OperationId = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RepoDir)) {
    $RepoDir = Split-Path -Parent $ScriptDir
}
$RepoDir = [IO.Path]::GetFullPath($RepoDir)
$RuntimeDir = Join-Path $RepoDir "instance\deployment"
$StateFile = Join-Path $RuntimeDir "gdt-controller-state.json"
$TokenFile = Join-Path $RuntimeDir "gdt-controller-token"
$PidFile = Join-Path $RuntimeDir "gdt-controller.pid"
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"
$EnvFile = Join-Path $RepoDir ".env"

. (Join-Path $ScriptDir "gdt-host-path.ps1")

function Write-AtomicUtf8 {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Value
    )
    $Parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    $Temporary = Join-Path $Parent (".{0}.{1}.tmp" -f ([IO.Path]::GetFileName($Path)), [Guid]::NewGuid().ToString("N"))
    [IO.File]::WriteAllText($Temporary, $Value, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $Temporary -Destination $Path -Force
}

function Write-JsonState {
    param([string] $Path, [hashtable] $Value)
    Write-AtomicUtf8 -Path $Path -Value ($Value | ConvertTo-Json -Depth 6 -Compress)
}

function Get-OperationPath {
    param([string] $Id)
    if ($Id -notmatch '^[a-f0-9]{32}$') {
        throw "Invalid operation identifier."
    }
    return Join-Path $RuntimeDir "operations\$Id.json"
}

function Read-JsonObject {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
}

function Get-ControllerToken {
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    if (-not (Test-Path -LiteralPath $TokenFile -PathType Leaf)) {
        $Bytes = New-Object byte[] 32
        [Security.Cryptography.RandomNumberGenerator]::Fill($Bytes)
        Write-AtomicUtf8 -Path $TokenFile -Value ([Convert]::ToBase64String($Bytes))
    }
    return (Get-Content -Raw -LiteralPath $TokenFile).Trim()
}

function Get-AllowedOrigins {
    return @(
        "http://127.0.0.1:$LabAppPort",
        "http://localhost:$LabAppPort"
    )
}

function Test-AllowedOrigin {
    param([string] $Origin)
    return -not [string]::IsNullOrWhiteSpace($Origin) -and (Get-AllowedOrigins) -contains $Origin
}

function Write-Response {
    param(
        [Parameter(Mandatory = $true)] $Context,
        [int] $StatusCode,
        [hashtable] $Body,
        [string] $Origin = ""
    )
    $Json = $Body | ConvertTo-Json -Depth 8 -Compress
    $Bytes = [Text.Encoding]::UTF8.GetBytes($Json)
    $Context.Response.StatusCode = $StatusCode
    $Context.Response.ContentType = "application/json; charset=utf-8"
    $Context.Response.ContentLength64 = $Bytes.Length
    if (Test-AllowedOrigin $Origin) {
        $Context.Response.Headers["Access-Control-Allow-Origin"] = $Origin
        $Context.Response.Headers["Vary"] = "Origin"
    }
    $Context.Response.OutputStream.Write($Bytes, 0, $Bytes.Length)
    $Context.Response.Close()
}

function Get-DeploymentStatus {
    $Selection = Get-GdtHostPathSelection `
        -RepoDir $RepoDir `
        -DeployDir $ScriptDir `
        -EnvFile $EnvFile `
        -StateFile $StateFile `
        -DefaultPath (Join-Path $RepoDir "instance\gdt-bridge")
    return @{
        state = "ready"
        effectiveHostPath = $Selection.Path
        desiredHostPath = $Selection.DesiredPath
        source = $Selection.Source
        conflict = $Selection.Conflict
        applicationPath = "/data/gdt-bridge"
        derived = @{
            inbox = "/data/gdt-bridge/inbox"
            outbox = "/data/gdt-bridge/outbox"
            processing = "/data/gdt-bridge/processing"
            archive = "/data/gdt-bridge/archive"
            error = "/data/gdt-bridge/error"
            diagnostic = "/data/gdt-bridge/diagnostic"
        }
    }
}

function Invoke-Compose {
    param([string[]] $Arguments, [string] $HostPath)
    [Environment]::SetEnvironmentVariable("GDT_BRIDGE_HOST_PATH", $HostPath, "Process")
    $Base = @("compose")
    if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
        $Base += @("--env-file", $EnvFile)
    }
    $Base += @("-f", $ComposeFile) + $Arguments
    & docker @Base
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose action failed with exit code $LASTEXITCODE."
    }
}

function Set-Operation {
    param([string] $Id, [string] $State, [string] $Stage, [string] $Message = "", [string] $HostPath = "")
    $Value = @{
        id = $Id
        state = $State
        stage = $Stage
        message = $Message
        updatedAt = [DateTimeOffset]::UtcNow.ToString("o")
    }
    if ($HostPath) {
        $Value.hostPath = $HostPath
    }
    Write-JsonState -Path (Get-OperationPath $Id) -Value $Value
}

function Invoke-ApplyWorker {
    param([string] $Id)
    $RequestPath = Join-Path $RuntimeDir "operations\$Id.request.json"
    try {
        $Request = Read-JsonObject -Path $RequestPath
        if ($null -eq $Request) {
            throw "Apply request is unavailable."
        }
        Set-Operation -Id $Id -State "running" -Stage "validating"
        $HostPath = Resolve-GdtHostPath `
            -Value ([string] $Request.hostPath) `
            -RepoDir $RepoDir `
            -DeployDir $ScriptDir `
            -RequireAbsolute
        Set-Operation -Id $Id -State "running" -Stage "provisioning" -HostPath $HostPath
        Initialize-GdtHostDirectories -Root $HostPath
        Set-Operation -Id $Id -State "running" -Stage "persisting" -HostPath $HostPath
        Write-JsonState -Path $StateFile -Value @{
            hostPath = $HostPath
            updatedAt = [DateTimeOffset]::UtcNow.ToString("o")
        }
        $Selection = Get-GdtHostPathSelection `
            -RepoDir $RepoDir -DeployDir $ScriptDir -EnvFile $EnvFile `
            -StateFile $StateFile -DefaultPath (Join-Path $RepoDir "instance\gdt-bridge")
        if ($Selection.Conflict) {
            throw "A higher-precedence process or .env override prevents the saved host path from becoming effective."
        }
        Set-Operation -Id $Id -State "running" -Stage "recreating" -HostPath $HostPath
        Invoke-Compose -Arguments @("up", "-d", "--force-recreate", "--no-deps", "lab-app") -HostPath $HostPath
        Set-Operation -Id $Id -State "running" -Stage "verifying" -HostPath $HostPath
        Invoke-Compose -Arguments @("ps", "lab-app") -HostPath $HostPath
        Set-Operation -Id $Id -State "succeeded" -Stage "completed" -HostPath $HostPath
    } catch {
        Set-Operation -Id $Id -State "failed" -Stage "failed" -Message $_.Exception.Message
    } finally {
        Remove-Item -LiteralPath $RequestPath -Force -ErrorAction SilentlyContinue
    }
}

function Start-ApplyOperation {
    param([string] $HostPath)
    $Running = Get-ChildItem -LiteralPath (Join-Path $RuntimeDir "operations") -Filter "*.json" -ErrorAction SilentlyContinue |
        ForEach-Object { Read-JsonObject -Path $_.FullName } |
        Where-Object { $_.state -in @("pending", "running") } |
        Select-Object -First 1
    if ($Running) {
        throw "A GDT host-path apply operation is already running."
    }
    $Id = [Guid]::NewGuid().ToString("N")
    $RequestPath = Join-Path $RuntimeDir "operations\$Id.request.json"
    Write-JsonState -Path $RequestPath -Value @{ hostPath = $HostPath }
    Set-Operation -Id $Id -State "pending" -Stage "queued"
    $PowerShell = (Get-Process -Id $PID).Path
    Start-Process -FilePath $PowerShell -WindowStyle Hidden -ArgumentList @(
        "-NoProfile", "-NonInteractive", "-File", $PSCommandPath,
        "-Mode", "worker", "-RepoDir", $RepoDir,
        "-Port", "$Port", "-LabAppPort", "$LabAppPort",
        "-OperationId", $Id
    ) | Out-Null
    return $Id
}

function Start-Controller {
    $Token = Get-ControllerToken
    Write-AtomicUtf8 -Path $PidFile -Value "$PID"
    $Listener = [Net.HttpListener]::new()
    $Listener.Prefixes.Add("http://127.0.0.1:$Port/")
    try {
        $Listener.Start()
        while ($Listener.IsListening) {
            $Context = $Listener.GetContext()
            $Request = $Context.Request
            $Origin = [string] $Request.Headers["Origin"]
            $Path = $Request.Url.AbsolutePath
            if (-not (Test-AllowedOrigin $Origin)) {
                Write-Response -Context $Context -StatusCode 403 -Body @{ error = "origin_not_allowed" }
                continue
            }
            if ($Request.HttpMethod -eq "OPTIONS") {
                $Context.Response.StatusCode = 204
                $Context.Response.Headers["Access-Control-Allow-Origin"] = $Origin
                $Context.Response.Headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                $Context.Response.Headers["Access-Control-Allow-Headers"] = "Content-Type, X-Healthcare-Lab-Controller"
                $Context.Response.Headers["Vary"] = "Origin"
                $Context.Response.Close()
                continue
            }
            if ($Request.HttpMethod -eq "GET" -and $Path -eq "/v1/session") {
                Write-Response -Context $Context -StatusCode 200 -Origin $Origin -Body @{
                    token = $Token
                    controllerUrl = "http://127.0.0.1:$Port"
                }
                continue
            }
            if ($Request.HttpMethod -eq "GET" -and $Path -eq "/v1/status") {
                Write-Response -Context $Context -StatusCode 200 -Origin $Origin -Body (Get-DeploymentStatus)
                continue
            }
            if ($Request.HttpMethod -eq "GET" -and $Path -match '^/v1/operations/([a-f0-9]{32})$') {
                $Operation = Read-JsonObject -Path (Get-OperationPath $Matches[1])
                if ($null -eq $Operation) {
                    Write-Response -Context $Context -StatusCode 404 -Origin $Origin -Body @{ error = "operation_not_found" }
                } else {
                    Write-Response -Context $Context -StatusCode 200 -Origin $Origin -Body @{
                        operation = $Operation
                    }
                }
                continue
            }
            if ($Request.HttpMethod -eq "POST" -and $Path -eq "/v1/apply") {
                if ($Request.Headers["X-Healthcare-Lab-Controller"] -cne $Token) {
                    Write-Response -Context $Context -StatusCode 403 -Origin $Origin -Body @{ error = "authorization_failed" }
                    continue
                }
                $Reader = [IO.StreamReader]::new($Request.InputStream, $Request.ContentEncoding)
                $Raw = $Reader.ReadToEnd()
                if ($Raw.Length -gt 4096) {
                    Write-Response -Context $Context -StatusCode 413 -Origin $Origin -Body @{ error = "request_too_large" }
                    continue
                }
                try {
                    $Body = $Raw | ConvertFrom-Json
                    $Properties = @($Body.PSObject.Properties.Name)
                    if ($Properties.Count -ne 1 -or $Properties[0] -ne "hostPath") {
                        throw "Only hostPath is supported."
                    }
                    Resolve-GdtHostPath -Value ([string] $Body.hostPath) -RepoDir $RepoDir -DeployDir $ScriptDir -RequireAbsolute | Out-Null
                    $Id = Start-ApplyOperation -HostPath ([string] $Body.hostPath)
                    Write-Response -Context $Context -StatusCode 202 -Origin $Origin -Body @{ operationId = $Id }
                } catch {
                    $Status = if ($_.Exception.Message -like "*already running*") { 409 } else { 400 }
                    Write-Response -Context $Context -StatusCode $Status -Origin $Origin -Body @{ error = "apply_rejected"; message = $_.Exception.Message }
                }
                continue
            }
            Write-Response -Context $Context -StatusCode 404 -Origin $Origin -Body @{ error = "not_found" }
        }
    } finally {
        $Listener.Close()
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
}

if ($Mode -eq "worker") {
    Invoke-ApplyWorker -Id $OperationId
} else {
    Start-Controller
}
