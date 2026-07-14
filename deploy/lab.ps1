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
