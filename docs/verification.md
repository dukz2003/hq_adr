# Verification record

## 2026-10-04, Windows development host

- 11 service unit tests passed (auth, fixed actions, input bounds, rate limit,
  redacted errors, no public signer, stable environment identity).
- 41 desktop Hongguo tests passed, including 7 new remote-mode tests.
- Started standalone API on localhost:18088 with its own Java process.
- Desktop CLI in remote mode retrieved all 99/99 episode models of series
  7686533063710346265; no missing streams.
- Downloaded episode 1 via remote mode to the existing local test-output folder;
  decryption/remux/full audio+video decode passed, 11.89 seconds.
- No video bytes pass through the API; Java runs only in the service process.

These are local API tests, not Railway deployment results. They do not demonstrate
that a Railway IP is accepted or that cross-IP CDN downloads work. Linux Docker
build/startup and Railway deployment must be verified separately.

No token, guest identity, content keys or CDN URLs are recorded here.
