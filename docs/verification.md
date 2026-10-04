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
Credential/guest-variable configuration and cloud tests were completed later
in the same session; see the Railway results below. Discovery alone was not
treated as deployment success.

No token, guest identity, content keys or CDN URLs are recorded here.

## Railway cloud results — 2026-10-04

- Service hq_adr: Deployment successful/ACTIVE; HTTPS origin
  https://hqadr-production.up.railway.app.
- Healthcheck HTTP 200 before and after the complete download.
- Missing service token: HTTP 401. Invalid series ID: HTTP 422.
  Authenticated /sign: HTTP 404 (native signer not publicly exposed).
- Cloud API listed all 99 episodes and provided all 99 stream models for
  series 7686533063710346265; missing_streams=[].
- Fresh output directory: 99 new verified downloads, 99 returned files,
  590.38 seconds, quality 1080p, 2 download workers.
- Every file passed remux/probe/full audio+video decode before atomic final save.
- Independent final manifest/hash audit: 99 files, 99 verified entries,
  99 distinct SHA-256 hashes, 720930792 bytes, no errors, all_passed=true.
- All final files: video HEVC 1080x1920, audio AAC, positive duration.
- Additional independent full FFmpeg decode of episode 1 and 99: both exit=0.
- Cold-process resume: 0 new downloads, 99 reused files, 3.94 seconds.
- Client machine had no running Java signer: signing/API calls were on Railway;
  videos downloaded directly from CDN to the Windows client.
- Regression: 164 desktop tests and 11 service tests passed.
- No paid-plan upgrade. The running service consumes finite Railway Trial credit;
  this is a successful single end-to-end run, not a long-term uptime/load guarantee.

Videos: D:\phuduc\test_hq_dl\test-output\railway-hongguo\亿万斯年.
Sanitized local reports: railway-download-report.json,
railway-manifest-audit.json, railway-resume-report.json in the parent test-output
directory. No secret values are uploaded with this record.
