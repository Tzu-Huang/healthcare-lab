$GdtBridgeDirectoryRoles = @(
    "inbox",
    "outbox",
    "processing",
    "archive",
    "error",
    "diagnostic"
)

function Get-GdtDotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Name
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

function Read-GdtControllerState {
    param([Parameter(Mandatory = $true)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        $State = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    } catch {
        throw "GDT controller deployment state is invalid."
    }
    if ([string]::IsNullOrWhiteSpace([string] $State.hostPath)) {
        throw "GDT controller deployment state is missing hostPath."
    }
    return [string] $State.hostPath
}

function Resolve-GdtHostPath {
    param(
        [Parameter(Mandatory = $true)][string] $Value,
        [Parameter(Mandatory = $true)][string] $RepoDir,
        [Parameter(Mandatory = $true)][string] $DeployDir,
        [switch] $RequireAbsolute,
        [string[]] $AdditionalRejectedPaths = @()
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "GDT host path is required."
    }
    if ($Value -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "GDT host path must not contain parent traversal."
    }
    if ($Value.StartsWith("\\") -or $Value.StartsWith("//")) {
        throw "GDT host path must be a local path, not a UNC path."
    }
    if ($RequireAbsolute -and -not [IO.Path]::IsPathRooted($Value)) {
        throw "GDT host path must be an absolute path."
    }

    $ResolvedPath = if ([IO.Path]::IsPathRooted($Value)) {
        [IO.Path]::GetFullPath($Value)
    } else {
        [IO.Path]::GetFullPath((Join-Path $RepoDir $Value))
    }
    $RootPath = [IO.Path]::GetPathRoot($ResolvedPath)
    $ComparablePath = $ResolvedPath.TrimEnd('\', '/')
    $RejectedPaths = @(
        [IO.Path]::GetFullPath($RepoDir),
        [IO.Path]::GetFullPath($DeployDir),
        [IO.Path]::GetFullPath($RootPath),
        [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    ) + $AdditionalRejectedPaths
    $RejectedPaths = $RejectedPaths |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { [IO.Path]::GetFullPath($_).TrimEnd('\', '/') }
    if ($RejectedPaths -contains $ComparablePath) {
        throw "GDT host path must identify a dedicated directory, not a broad filesystem, repository, deployment, or user-profile path."
    }
    if (Test-Path -LiteralPath $ResolvedPath -PathType Leaf) {
        throw "GDT host path must identify a directory."
    }
    return $ResolvedPath
}

function Get-GdtHostPathSelection {
    param(
        [Parameter(Mandatory = $true)][string] $RepoDir,
        [Parameter(Mandatory = $true)][string] $DeployDir,
        [Parameter(Mandatory = $true)][string] $EnvFile,
        [Parameter(Mandatory = $true)][string] $StateFile,
        [Parameter(Mandatory = $true)][string] $DefaultPath
    )

    $ProcessValue = [Environment]::GetEnvironmentVariable("GDT_BRIDGE_HOST_PATH")
    $EnvValue = Get-GdtDotEnvValue -Path $EnvFile -Name "GDT_BRIDGE_HOST_PATH"
    $StateValue = Read-GdtControllerState -Path $StateFile
    $Source = "default"
    $Value = $DefaultPath
    if (-not [string]::IsNullOrWhiteSpace($StateValue)) {
        $Source = "controller"
        $Value = $StateValue
    }
    if (-not [string]::IsNullOrWhiteSpace($EnvValue)) {
        $Source = "env-file"
        $Value = $EnvValue
    }
    if (-not [string]::IsNullOrWhiteSpace($ProcessValue)) {
        $Source = "process"
        $Value = $ProcessValue
    }
    $Resolved = Resolve-GdtHostPath -Value $Value -RepoDir $RepoDir -DeployDir $DeployDir
    return [pscustomobject]@{
        Path = $Resolved
        Source = $Source
        DesiredPath = if ($StateValue) {
            Resolve-GdtHostPath -Value $StateValue -RepoDir $RepoDir -DeployDir $DeployDir -RequireAbsolute
        } else {
            $null
        }
        Conflict = [bool]($StateValue -and $Source -ne "controller")
    }
}

function Initialize-GdtHostDirectories {
    param([Parameter(Mandatory = $true)][string] $Root)

    New-Item -ItemType Directory -Path $Root -Force | Out-Null
    foreach ($Role in $GdtBridgeDirectoryRoles) {
        New-Item -ItemType Directory -Path (Join-Path $Root $Role) -Force | Out-Null
    }
}
