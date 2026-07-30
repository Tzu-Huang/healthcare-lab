function Get-DockerComposeCommand {
    $Docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($Docker) {
        try {
            & $Docker.Source compose version *> $null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    FilePath = $Docker.Source
                    Prefix = @("compose")
                    DisplayName = "docker compose"
                }
            }
        } catch {
            # Fall through to the legacy standalone command.
        }
    }

    $Legacy = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($Legacy) {
        return @{
            FilePath = $Legacy.Source
            Prefix = @()
            DisplayName = "docker-compose"
        }
    }

    throw "Docker Compose is unavailable. Install Docker Compose v2 or the legacy docker-compose command."
}

function Get-DockerComposeInvocation {
    param([string[]] $Arguments)

    $Command = Get-DockerComposeCommand
    return @{
        FilePath = $Command.FilePath
        Arguments = @($Command.Prefix) + $Arguments
        DisplayName = $Command.DisplayName
    }
}
