# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | :white_check_mark: |
| < 1.3   | :x:                |

## Local CDP Security Trade-off

To inject the live quota badge into the Antigravity Desktop title bar, the default launcher configuration passes `--remote-debugging-port=0`. This binds a Chrome DevTools Protocol (CDP) socket to the `127.0.0.1` loopback interface, meaning other local processes running under the same OS user account could attach via CDP (e.g., `Runtime.evaluate`). This local attack surface is why Antigravity Desktop `2.33.0+` made remote debugging opt-in by default.

Users who prefer strict process isolation and want the MCP quota tools and background desktop notifications without opening any CDP debug port can skip the CDP launcher overrides during installation (keeping the default `AGY_UI_INJECTION_ENABLED=true`):

```bash
./install.sh --no-cdp-launcher
```

To stop the background watcher thread (`UIWatcherThread`) entirely—disabling **both** automatic UI badge injection and background desktop notifications so that only on-demand MCP stdio tools (`get_quota_status`, `clean_scratch_cache`, etc.) remain active—set `AGY_UI_INJECTION_ENABLED=false`.

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Email:** Send details directly to `info@mefamex.com` or via GitHub Private Vulnerability Reporting.
2. **Details:** Include a clear description, reproduction steps, and potential impact.
3. **Response:** You will receive an acknowledgment within 48 hours.

Please do not open public issues for security vulnerabilities until a patch is released.
