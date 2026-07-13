# User Preferences

- When the user names a specific reference location, such as `knowledge-base`, and it cannot be found in the workspace, stop and confirm the correct location with the user before proceeding. Do not silently substitute repo-local docs or inferred references.
- Read Markdown files with explicit UTF-8 encoding by default, especially knowledge-base or Chinese-language Markdown. On PowerShell, use `Get-Content -Encoding UTF8` instead of relying on the system default encoding.
