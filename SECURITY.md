# Security Policy

## Supported Versions

Security fixes are applied to the latest published release and the default
branch. Upgrade to the latest release before reporting an issue that may already
be fixed.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability or include exploit
details, credentials, patient data, or private infrastructure information in a
public discussion.

Use GitHub's **Report a vulnerability** option in the repository Security tab
to send a private report. Include:

- the affected version or commit;
- the component and deployment mode;
- reproduction steps using synthetic data;
- the likely impact; and
- any suggested mitigation.

If private vulnerability reporting is unavailable, contact the repository owner
privately through their GitHub profile before disclosing details.

## Deployment Boundary

Healthcare Lab is designed for trusted local or internal test environments with
virtual data. The default stack does not provide production-grade TLS,
authentication, authorization, regulated audit controls, or public-Internet
hardening. The `lab-app` container can access the Docker socket and therefore
has Docker-host administrative capability.
