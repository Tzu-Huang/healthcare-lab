## Context

The supported runtime is a Linux `lab-app` container on Docker Desktop for Windows. The application sees the GDT bridge at `/data/gdt-bridge`, while Docker Compose resolves `GDT_BRIDGE_HOST_PATH` on the host. Typed application settings cannot grant a running container access to a new Windows folder, and changing a bind mount requires container recreation.

The existing wrapper already validates dedicated host paths and recreates Compose services. The new design turns that logic into a narrowly scoped localhost control surface rather than allowing the container to rewrite its own deployment through the Docker socket.

## Goals / Non-Goals

**Goals:**

- Provide one GDT UI field for a Windows absolute bridge root.
- Safely create the documented directory contract and recreate only `lab-app`.
- Keep deployment path ownership distinct from typed GDT protocol/watcher settings.
- Survive wrapper restart and compatible application image replacement.
- Report bounded progress and recoverable failures without exposing directory contents.

**Non-Goals:**

- General-purpose Compose, filesystem, command, or environment editing through HTTP.
- Arbitrary bind mounts, multiple GDT roots, remote administration, or non-Windows host automation in the first supported version.
- Mounting a drive, repository root, user profile root, or another broad filesystem scope.
- Removing advanced `.env` compatibility.

## Decisions

### Use a host-side PowerShell controller managed by the deployment wrapper

`deploy/lab.ps1 start` will ensure a single controller instance is running, and `stop all` will stop the owned instance. The controller will expose only GDT host-path status and apply operations. It will reuse shared validation/recreation functions rather than accepting commands.

Running the operation inside `lab-app` was rejected because the container cannot safely create Windows paths and self-recreation through the Docker socket would couple application identity to deployment mutation.

### Let the browser call the localhost controller directly

The browser already runs on the Windows operator host and can reach a loopback-only listener. Requests will require an exact allowed Healthcare Lab origin, a non-simple custom header, a bounded JSON schema, and an installation-scoped token obtained through the same-origin application session. The controller will reject absent/null origins and will not enable wildcard CORS.

Binding a controller broadly for `host.docker.internal` was rejected because it increases network exposure. A general local daemon API was rejected because the required authority is only one GDT operation.

### Persist deployment state separately from `.env` and typed settings

The controller will atomically store only the normalized GDT host root in an ignored, host-local deployment state file. The wrapper will load this value into its own process environment before invoking Compose. An explicit process environment or documented `.env` override remains higher precedence, and the UI will identify when an external override prevents a saved controller value from becoming effective.

The typed GDT profile continues to own enabled state, identities, filename behavior, and watcher timing. Its application path remains `/data/gdt-bridge`.

### Apply one root and derive all subdirectories

The request contains a single absolute host root. The controller rejects empty, relative, UNC, traversal-containing, drive-root, repository-root, deployment-root, and user-profile-root targets, as well as existing files. It creates only the root plus `inbox`, `outbox`, `processing`, `archive`, `error`, and `diagnostic`.

The UI will no longer ask operators to coordinate separate inbox/outbox values. Container-visible paths are derived from the fixed mount target.

### Use an asynchronous apply state machine

Apply returns an operation identifier before recreation. The UI polls bounded status states: `validating`, `provisioning`, `persisting`, `recreating`, `verifying`, `succeeded`, or `failed`. Only one apply operation may run at a time. Verification confirms the replacement container reports the requested effective host source and healthy bounded GDT diagnostics.

This avoids relying on the HTTP connection to `lab-app`, which is intentionally interrupted during recreation.

## Risks / Trade-offs

- **[Local controller increases host authority]** → Limit it to loopback, one schema, one Compose service, fixed functions, strict origin/token checks, redacted logs, and no shell-command input.
- **[Browser origin varies with configured app port]** → Derive an exact allowlist from wrapper-owned local app endpoints and reject non-loopback origins by default.
- **[A recreate can interrupt active GDT work]** → Require explicit confirmation, stop/quiesce the watcher, serialize operations, and surface interruption/retry guidance.
- **[Power loss can occur between persistence and recreation]** → Use atomic state writes; on the next wrapper start, reconcile Compose from the durable desired value.
- **[External `.env` or process overrides can conflict]** → Return desired and effective sources separately and never silently overwrite an advanced operator override.
- **[Controller startup can fail]** → Keep the application usable, mark UI apply unavailable, and provide a bounded wrapper command fallback.

## Migration Plan

1. Add controller scripts, ignored deployment-state location, wrapper lifecycle, and contract tests while retaining current `.env` behavior.
2. Add read-only controller discovery and status to the UI.
3. Enable apply/recreate and post-restart verification.
4. Replace editable GDT inbox/outbox fields with one host root while retaining derived read-only paths.
5. Update release documentation and verify clean start, retained restart, path change, conflict, failure, and rollback cases.

Rollback stops the controller and returns the UI to read-only host metadata. Existing `.env` or default Compose interpolation continues to select the bind path; typed GDT settings and bridge data remain unchanged.

## Open Questions

- Whether the initial supported origin allowlist should include both `localhost` and `127.0.0.1` for every configured `LAB_APP_PORT`, or only the exact URL used to open the UI.
- Whether an active watcher should be automatically quiesced and restored or require the operator to stop it before apply.
