# Hongguo metadata API (Python + Java 21)

Standalone service for `tool_video_tts_stt`. The server owns the guest identity,
Java/unidbg signer and Hongguo metadata requests. Desktop clients download video
directly from the returned CDN URL, then decrypt/remux/validate locally.
No video storage/proxy, paid signing API, Android app or TTS/STT dependencies.

## Security and provenance

- Protected endpoints require `Authorization: Bearer <HQ_API_TOKEN>`.
- Generate a private random token of at least 32 characters. Never commit it.
- `/healthz` is public; `/sign`, docs and generic URL/proxy endpoints are not exposed.
- Java only listens on loopback. One worker serializes upstream work; queue and
  request rate are bounded. No access logging of CDN links or content keys.
- The response includes sensitive short-lived URLs/encryption metadata. HTTPS,
  trusted clients and authorized content access are required.
- A shared token is for a private trial, NOT sufficient licensing/authentication
  for a publicly distributed EXE. Issue per-user credentials before public release;
  a token embedded in an EXE can be extracted.
- Preserve `hq_service/assets/NOTICE.md` and `manifest.json`. The signer resources
  came from zhangbaio/hongguo commit 5f8a58d; redistribution rights are not established
  by this integration. Review upstream/native-library terms before public releases.
- No claim that guest access will continue working or that locked/paid content can
  be accessed. Stop on denied access/verification; do not rotate IDs to evade limits.

## Railway

1. Deploy this repository as a service; `Dockerfile` and `railway.toml` are included.
2. Configure `HQ_API_TOKEN` in Railway Variables, never in Git.
3. Configure all three `HQ_DEVICE_ID`, `HQ_IID`, `HQ_CDID` from a single stable
   private guest profile. Railway ephemeral disks otherwise lose the profile on
   redeploy. Do not change identity on rate limits. Do not publish these values.
4. Generate an HTTPS Railway domain on the service's assigned `PORT`.
5. Health check `/healthz` only becomes ready after Java/assets pass startup checks.
   It does not prove Hongguo accepts the host's IP or the returned CDN URLs.
6. Set desktop `.env`:

   ```dotenv
   HONGGUO_SERVICE_URL=https://your-service.up.railway.app
   HONGGUO_SERVICE_TOKEN=<same private token>
   HONGGUO_DOWNLOAD_WORKERS=2
   ```

7. Restart the desktop/backend. Remote mode does not start local Java, does not
   fall back silently, and currently requires a numeric series ID or a detail URL
   containing `series_id` (short share links are not supported in remote mode).
8. Test ALL episode models and a real download from the desktop's different IP.
   CDN links expire; retry requests refreshed models. Do not save keys/URLs in reports.

Railway Trial/Free has credit, RAM and possibly outbound-network limits. Do not
upgrade without the owner's approval. Java heap is capped at 384 MiB; actual
process RAM also includes native/emulator memory and Python. Measure before scaling.
Use a single replica; caches/queue/rate limits here are process-local.

## VPS migration

Use the same Docker image and variables. Example (PowerShell or bash):

```sh
docker build -t hq-metadata .
docker run -d --name hq-metadata --restart unless-stopped --env-file .env -p 127.0.0.1:8080:8080 hq-metadata
```

Put a TLS reverse proxy in front of localhost:8080, set firewall rules and keep
the signer private. Change only `HONGGUO_SERVICE_URL` on desktop. Set all stable
identity variables, or mount a private persistent writable data directory owned
by UID 10001. Docker does not contain FFmpeg because videos are processed locally.

## API v1

- `GET /healthz`: public readiness/version, no credentials.
- `GET /v1/series/{series_id}`: complete ordered episode list; partial data fails.
- `POST /v1/models`: `{ "vids": ["..."], "refresh": false }`, max 50 IDs; returns
  `models`, short client cache TTL and fixed download headers. Quality selection
  and offline spade-v1 handling remain in the existing desktop downloader.
- `GET /v1/search?keyword=...&limit=20`.
- `GET /v1/summary/{series_id}`, `/v1/rating/{series_id}`, `/v1/metadata/{series_id}`.

401: service token missing/wrong. 403: upstream access denied. 429: private API
rate limit, wait. 503: queue full/signer unavailable. 502: upstream/schema failure.
Never send arbitrary upstream URLs or signing headers to this API.

## Tests

```sh
python -m pip install -r requirements.txt httpx
python -m unittest discover -s tests -v
```

Unit tests mock upstream; deployment and real video tests must be recorded separately.
Local development can use `HQ_API_TOKEN` and `python -m hq_service`; default port
8080. `.env` is a Docker env-file, not automatically loaded by the Python service.
