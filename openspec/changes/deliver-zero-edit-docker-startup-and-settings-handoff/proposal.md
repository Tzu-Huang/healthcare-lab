## Why

Healthcare Lab's supported Docker quick start still requires operators to copy and edit a repository-root `.env` even though application-level integration configuration now has persisted Settings ownership. This makes a clean local deployment fail before the application can guide the operator, duplicates runtime settings across deployment and application layers, and leaves upgrade precedence unclear.

## What Changes

- Make the supported Compose release and `deploy/lab.ps1` start, inspect, status, restart, smoke, logs, and stop flows work predictably when no repository-root `.env` exists.
- Keep immutable image selections, supported host publications, service database credentials, bind-mount selection, and other deployment-only overrides available through Compose interpolation with safe local fallbacks.
- Provision the supported local application instance and GDT bridge directory contract without asking operators to edit Compose YAML.
- Reduce `.env.example` to documented advanced deployment and compatibility-bootstrap overrides, removing application-owned integration credentials and duplicated runtime endpoints from the normal Quick Start path.
- Preserve existing installations by seeding missing typed profiles once from eligible legacy environment values while keeping persisted Settings authoritative on later starts.
- Add a Dashboard setup notice that derives its state and destination from the existing secret-safe Settings readiness contract when required setup is incomplete.
- Keep secrets out of Compose, tracked files, browser storage, wrapper output, diagnostics, and generated evidence, and keep Docker/Compose mutation outside the web application's authority.
- Add contract coverage for Compose interpolation without `.env`, wrapper behavior, first-run and upgrade migration, persistence across container recreation, override compatibility, and secret-safe output.
- Rewrite Quick Start and deployment documentation to distinguish normal application setup in Settings from advanced deployment overrides.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-container-release`: Make zero-edit startup without a repository-root `.env` part of the supported release, wrapper, persistence, and advanced-override contract.
- `healthcare-lab-typed-integration-settings`: Clarify legacy environment migration and persisted precedence when `.env` is optional rather than a required runtime source.
- `healthcare-lab-settings-workspace`: Expose incomplete required readiness on the Dashboard and route the operator into the authoritative guided Settings flow.

## Impact

The change affects `deploy/docker-compose.yml`, `deploy/lab.ps1`, `.env.example`, deployment and root documentation, configuration ownership declarations, application composition/bootstrap seams, Dashboard navigation and presentation, and focused deployment/settings/frontend tests. It does not add production authentication or secret management, allow the web application to edit Compose, or permit arbitrary Docker commands.
