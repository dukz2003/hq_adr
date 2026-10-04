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

## Linux Docker verification on the development host

- Built the Docker image successfully for Linux x86_64 with Java 21.
- Started the service as non-root UID 10001; /healthz returned status=ok after
  bundled-resource checks and Java signer startup.
- Desktop remote-mode probe retrieved all 99/99 models through the Linux API.
- Downloaded episode 1 through the Linux metadata API to the desktop and passed
  decryption/remux/full audio+video decode in 11.70 seconds.
- A one-time idle memory observation after the probe was about 152 MiB for the
  container. This is not a peak/load measurement or a guarantee for Railway Free.
- Expanded desktop regression run: 164 tests passed. An earlier command used a
  nonexistent test module name; rerunning with test_media_error_handling succeeded.

GitHub repository is now public (changed by the owner). Railway accepted its full
URL and created project 6283028e-ed47-43be-90ad-f871916aa03a, service hq_adr.
Credential/guest-variable configuration and actual cloud acceptance/download
tests are still pending; repository discovery is not deployment success.

No token, guest identity, content keys or CDN URLs are recorded here.
