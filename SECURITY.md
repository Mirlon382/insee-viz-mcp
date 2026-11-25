# Security policy

## Reporting a vulnerability

Open a [private security advisory](https://github.com/Mirlon382/insee-viz-mcp/security/advisories/new)
rather than a public issue. Expect an answer within a week.

## What this server does and does not protect

Being explicit is more useful than a badge.

- **No authentication.** An HTTP deployment serves whoever can reach the port. Put it behind a
  gateway, a VPN or an auth proxy before exposing it. The container and the systemd unit both bind
  loopback for that reason, and `stdio` has no network surface at all.
- **`ALLOWED_HOSTS` defaults to `["*"]`** and logs a warning at startup: it accepts any `Host`
  header. Set the real hostname before publishing, or host-origin protection is decoration.
- **Rate limiting is per process and in memory.** Two replicas allow twice the traffic, and a
  restart resets the counters.
- **`mask_error_details=True` is deliberate.** Only `AppToolError` text is public, so never put a
  token, an internal URL or a stack trace in a tool's error message — including the new
  output-directory failure, which quotes the path on purpose.
- **The rendered files are not served.** Figures land in `INSEE_VIZ_OUT` (a `ui://` payload and a
  path in the tool result point at them). Nothing exposes that directory over HTTP; a volume or a
  bind mount is the only way to read it, and it holds nothing but figures.
- **The MCP App viewer runs untrusted data.** `structuredContent` came from a model's call and
  crosses into the iframe's DOM; the viewer must keep treating it as text. It loads the MCP Apps SDK
  from unpkg, declared in the resource CSP — pin or vendor it if that origin worries you.

## Scope

Vulnerabilities in this repository's own code — the middleware chain, host/origin protection, the
error contract, the SVG renderers, the viewer, the container image and the Kubernetes manifest — are
in scope. A weakness in a client that consumes the server, or in an Insee/IGN data source, is not.
