[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("status", "inspect", "start", "stop", "restart", "smoke", "logs", "controller-status")]
    [string] $Action = "status",

    [Parameter(Position = 1)]
    [string] $Service = "all",

    [int] $Lines = 200
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"
$EnvFile = Join-Path $RepoDir ".env"
$DefaultGdtBridgePath = Join-Path $RepoDir "instance\gdt-bridge"
$ControllerStateFile = Join-Path $RepoDir "instance\deployment\gdt-controller-state.json"
$ControllerPidFile = Join-Path $RepoDir "instance\deployment\gdt-controller.pid"
$ControllerScript = Join-Path $ScriptDir "gdt-host-controller.ps1"
$ControllerPort = 5010

. (Join-Path $ScriptDir "gdt-host-path.ps1")

$ServiceMap = @{
    "all" = @()
    "oie" = @("oie")
    "medplum" = @("medplum", "medplum-app")
    "medplum-postgres" = @("medplum-postgres")
    "medplum-redis" = @("medplum-redis")
    "medplum-app" = @("medplum-app")
    "gdt-bridge" = @("lab-app")
    "dcm4chee" = @("dcm4chee")
    "dcm4chee-db" = @("dcm4chee-db")
    "ldap" = @("ldap")
    "hl7tester" = @("lab-app")
    "gdt-hospital" = @("lab-app")
    "lab-app" = @("lab-app")
}

function Resolve-LabService {
    param([string] $Name)

    $Key = $Name.Trim().ToLowerInvariant()
    if (-not $ServiceMap.ContainsKey($Key)) {
        $Allowed = ($ServiceMap.Keys | Sort-Object) -join ", "
        throw "Unsupported service '$Name'. Allowed values: $Allowed."
    }
    return $ServiceMap[$Key]
}

function Resolve-GdtBridgeHostPath {
    return (Get-GdtHostPathSelection `
        -RepoDir $RepoDir `
        -DeployDir $ScriptDir `
        -EnvFile $EnvFile `
        -StateFile $ControllerStateFile `
        -DefaultPath $DefaultGdtBridgePath).Path
}

function Initialize-LabDirectories {
    $GdtBridgePath = Resolve-GdtBridgeHostPath
    Initialize-GdtHostDirectories -Root $GdtBridgePath
    [Environment]::SetEnvironmentVariable(
        "GDT_BRIDGE_HOST_PATH",
        $GdtBridgePath,
        [EnvironmentVariableTarget]::Process
    )
}

function Get-ControllerProcess {
    if (-not (Test-Path -LiteralPath $ControllerPidFile -PathType Leaf)) {
        return $null
    }
    try {
        $Identity = Get-Content -Raw -LiteralPath $ControllerPidFile | ConvertFrom-Json
    } catch {
        Remove-Item -LiteralPath $ControllerPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    if ($Identity.pid -notmatch '^\d+$' -or
        -not ([string] $Identity.scriptPath).Equals(
            [IO.Path]::GetFullPath($ControllerScript),
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not ([string] $Identity.repoDir).Equals(
            [IO.Path]::GetFullPath($RepoDir),
            [StringComparison]::OrdinalIgnoreCase
        )) {
        Remove-Item -LiteralPath $ControllerPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    $Controller = Get-Process -Id ([int] $Identity.pid) -ErrorAction SilentlyContinue
    if (-not $Controller) {
        Remove-Item -LiteralPath $ControllerPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    $CommandLine = if ($IsWindows -or $env:OS -eq "Windows_NT") {
        (Get-CimInstance Win32_Process -Filter "ProcessId = $($Controller.Id)" -ErrorAction SilentlyContinue).CommandLine
    } else {
        (& ps -p $Controller.Id -o args= 2>$null | Out-String).Trim()
    }
    # Some locked-down Windows environments allow Get-Process but deny WMI/CIM
    # command-line reads. The installation-scoped identity plus the expected
    # PowerShell executable still identifies the owned controller; do not
    # destroy its identity merely because the optional stronger check is
    # unavailable.
    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        if ($Controller.ProcessName -in @("powershell", "pwsh")) {
            return $Controller
        }
        Remove-Item -LiteralPath $ControllerPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    if ($CommandLine.IndexOf([IO.Path]::GetFullPath($ControllerScript), [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $CommandLine.IndexOf("-Mode serve", [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $CommandLine.IndexOf([IO.Path]::GetFullPath($RepoDir), [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        Remove-Item -LiteralPath $ControllerPidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
    return $Controller
}

function Start-GdtHostController {
    if ($env:HEALTHCARE_LAB_DISABLE_HOST_CONTROLLER -eq "1") {
        return
    }
    if (Get-ControllerProcess) {
        return
    }
    $PowerShell = (Get-Process -Id $PID).Path
    $InheritedGdtPath = $env:GDT_BRIDGE_HOST_PATH
    try {
        Remove-Item Env:GDT_BRIDGE_HOST_PATH -ErrorAction SilentlyContinue
        Start-Process -FilePath $PowerShell -WindowStyle Hidden -ArgumentList @(
            "-NoProfile", "-NonInteractive", "-File", $ControllerScript,
            "-Mode", "serve", "-RepoDir", $RepoDir,
            "-Port", "$ControllerPort", "-LabAppPort", "$env:LAB_APP_PORT"
        ) | Out-Null
    } finally {
        $env:GDT_BRIDGE_HOST_PATH = $InheritedGdtPath
    }
}

function Stop-GdtHostController {
    if ($env:HEALTHCARE_LAB_DISABLE_HOST_CONTROLLER -eq "1") {
        return
    }
    $Controller = Get-ControllerProcess
    if ($Controller) {
        Stop-Process -Id $Controller.Id
    }
    Remove-Item -LiteralPath $ControllerPidFile -Force -ErrorAction SilentlyContinue
}

function Invoke-DockerCompose {
    param([string[]] $Arguments)

    $BaseArgs = @("compose")
    if (Test-Path $EnvFile) {
        $BaseArgs += @("--env-file", $EnvFile)
    }
    $BaseArgs += @("-f", $ComposeFile) + $Arguments
    & docker @BaseArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($BaseArgs -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Invoke-Smoke {
    param([string[]] $Services)

    Invoke-DockerCompose @("ps")
    if ($Services.Count -gt 0) {
        foreach ($Item in $Services) {
            Invoke-DockerCompose @("ps", $Item)
        }
    }
}

$ResolvedServices = @(Resolve-LabService $Service)

switch ($Action) {
    "inspect" {
        Invoke-DockerCompose (@("ps", "--all", "--format", "json") + $ResolvedServices)
    }
    "status" {
        if ($ResolvedServices.Count -eq 0) {
            Invoke-DockerCompose @("ps")
        } else {
            Invoke-DockerCompose (@("ps") + $ResolvedServices)
        }
    }
    "start" {
        Initialize-LabDirectories
        if ([string]::IsNullOrWhiteSpace($env:LAB_APP_PORT)) {
            $env:LAB_APP_PORT = Get-GdtDotEnvValue -Path $EnvFile -Name "LAB_APP_PORT"
        }
        if ([string]::IsNullOrWhiteSpace($env:LAB_APP_PORT)) {
            $env:LAB_APP_PORT = "5000"
        }
        Start-GdtHostController
        Invoke-DockerCompose (@("up", "-d") + $ResolvedServices)
    }
    "stop" {
        if ($ResolvedServices.Count -eq 0) {
            Invoke-DockerCompose @("stop")
            Stop-GdtHostController
        } else {
            Invoke-DockerCompose (@("stop") + $ResolvedServices)
        }
    }
    "restart" {
        if ([string]::IsNullOrWhiteSpace($env:LAB_APP_PORT)) {
            $env:LAB_APP_PORT = Get-GdtDotEnvValue -Path $EnvFile -Name "LAB_APP_PORT"
        }
        if ([string]::IsNullOrWhiteSpace($env:LAB_APP_PORT)) {
            $env:LAB_APP_PORT = "5000"
        }
        Start-GdtHostController
        if ($ResolvedServices.Count -eq 0) {
            Initialize-LabDirectories
        }
        if ($ResolvedServices.Count -eq 0) {
            Invoke-DockerCompose @("up", "-d", "--force-recreate")
        } else {
            Invoke-DockerCompose (@("up", "-d", "--force-recreate", "--no-deps") + $ResolvedServices)
        }
    }
    "smoke" {
        Invoke-Smoke $ResolvedServices
    }
    "logs" {
        $Tail = [Math]::Max(1, $Lines)
        if ($ResolvedServices.Count -eq 0) {
            Invoke-DockerCompose @("logs", "--tail", "$Tail")
        } else {
            Invoke-DockerCompose (@("logs", "--tail", "$Tail") + $ResolvedServices)
        }
    }
    "controller-status" {
        $Controller = Get-ControllerProcess
        if ($Controller) {
            Write-Output "GDT host controller is running."
        } else {
            Write-Output "GDT host controller is stopped."
        }
    }
}
