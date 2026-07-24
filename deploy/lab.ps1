[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("status", "inspect", "start", "stop", "restart", "smoke", "logs")]
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

function Get-DotEnvValue {
    param(
        [string] $Path,
        [string] $Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    foreach ($Line in Get-Content -LiteralPath $Path) {
        if ($Line -match "^\s*(?:export\s+)?$([Regex]::Escape($Name))\s*=(.*)$") {
            $Value = $Matches[1].Trim()
            if (
                $Value.Length -ge 2 -and
                (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or
                 ($Value.StartsWith("'") -and $Value.EndsWith("'")))
            ) {
                $Value = $Value.Substring(1, $Value.Length - 2)
            }
            return $Value
        }
    }
    return $null
}

function Resolve-GdtBridgeHostPath {
    $ConfiguredPath = [Environment]::GetEnvironmentVariable("GDT_BRIDGE_HOST_PATH")
    if ([string]::IsNullOrWhiteSpace($ConfiguredPath)) {
        $ConfiguredPath = Get-DotEnvValue -Path $EnvFile -Name "GDT_BRIDGE_HOST_PATH"
    }
    if ([string]::IsNullOrWhiteSpace($ConfiguredPath)) {
        return [IO.Path]::GetFullPath($DefaultGdtBridgePath)
    }

    if ([IO.Path]::IsPathRooted($ConfiguredPath)) {
        $ResolvedPath = [IO.Path]::GetFullPath($ConfiguredPath)
    } else {
        $ResolvedPath = [IO.Path]::GetFullPath((Join-Path $RepoDir $ConfiguredPath))
    }

    $RootPath = [IO.Path]::GetPathRoot($ResolvedPath)
    $ComparablePath = $ResolvedPath.TrimEnd('\', '/')
    $RejectedPaths = @(
        [IO.Path]::GetFullPath($RepoDir),
        [IO.Path]::GetFullPath($ScriptDir),
        [IO.Path]::GetFullPath($RootPath)
    ) | ForEach-Object { $_.TrimEnd('\', '/') }
    if ($RejectedPaths -contains $ComparablePath) {
        throw "GDT_BRIDGE_HOST_PATH must identify a dedicated directory, not a broad filesystem or repository path."
    }
    if (Test-Path -LiteralPath $ResolvedPath -PathType Leaf) {
        throw "GDT_BRIDGE_HOST_PATH must identify a directory."
    }
    return $ResolvedPath
}

function Initialize-LabDirectories {
    $GdtBridgePath = Resolve-GdtBridgeHostPath
    New-Item -ItemType Directory -Path $GdtBridgePath -Force | Out-Null
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
        Invoke-DockerCompose (@("up", "-d") + $ResolvedServices)
    }
    "stop" {
        if ($ResolvedServices.Count -eq 0) {
            Invoke-DockerCompose @("stop")
        } else {
            Invoke-DockerCompose (@("stop") + $ResolvedServices)
        }
    }
    "restart" {
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
}
