"""Authenticated metadata-only API; never expose the native /sign listener."""
from __future__ import annotations

import asyncio
import hmac
import os
import re
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from hq_service import client, signer

ID_PATTERN = r'^\d{15,25}$'


@asynccontextmanager
async def lifespan(app):
    token = os.getenv('HQ_API_TOKEN', '').strip()
    if len(token) < 32 or token.lower().startswith(('changeme', 'replace')):
        raise RuntimeError('HQ_API_TOKEN must be a private random token of at least 32 characters.')
    app.state.token = token
    app.state.calls = deque()
    app.state.rate = max(1, int(os.getenv('HQ_RATE_LIMIT_PER_MINUTE', '60')))
    app.state.pending = 0
    app.state.max_pending = max(1, min(16, int(os.getenv('HQ_MAX_PENDING', '4'))))
    app.state.work_lock = asyncio.Lock()
    try:
        # Fail the deployment health check on missing Java/assets, not the first user download.
        await run_in_threadpool(client._guest_identity)
        await run_in_threadpool(signer._ensure_server)
        yield
    finally:
        signer.close()


app = FastAPI(title='Hongguo metadata service', version='1.0.0',
              lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def guard(request: Request, call_next):
    if request.url.path != '/healthz':
        expected = 'Bearer ' + request.app.state.token
        if not hmac.compare_digest(request.headers.get('authorization', '').encode(), expected.encode()):
            return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
        now = time.monotonic()
        calls = request.app.state.calls
        while calls and calls[0] <= now - 60:
            calls.popleft()
        if len(calls) >= request.app.state.rate:
            return JSONResponse({'detail': 'Service rate limit; wait before retrying.'},
                                status_code=429, headers={'Retry-After': '60'})
        calls.append(now)
        if request.method == 'POST':
            try:
                length = int(request.headers.get('content-length', '-1'))
            except ValueError:
                length = -1
            if not 0 <= length <= 65536:
                return JSONResponse({'detail': 'A body of at most 64 KiB with Content-Length is required.'},
                                    status_code=413)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


async def upstream(function, *args):
    state = app.state
    if state.pending >= state.max_pending:
        raise HTTPException(503, 'Service busy; retry later.', headers={'Retry-After': '5'})
    state.pending += 1
    try:
        async with state.work_lock:
            return await run_in_threadpool(function, *args)
    except client.AccessDeniedError:
        raise HTTPException(403, 'Hongguo rejected access or rate-limited the guest. Do not rotate IDs.') from None
    except signer.SignerError:
        raise HTTPException(503, 'Signer unavailable. The server operator must check Java/assets.') from None
    except (ValueError, RuntimeError, OSError):
        # Upstream exceptions may contain URLs/keys: never return them to logs or clients.
        raise HTTPException(502, 'Hongguo upstream failed. Check server runtime, API compatibility and access.') from None
    finally:
        state.pending -= 1


def checked_id(value):
    if not re.fullmatch(ID_PATTERN, value):
        raise HTTPException(422, 'Invalid series ID.')
    return value


@app.get('/healthz')
async def health():
    return {'status': 'ok', 'api_version': 1, 'video_proxy': False}


@app.get('/v1/series/{series_id}')
async def series(series_id: str):
    return await upstream(client.fetch_episode_list, checked_id(series_id))


class ModelsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    vids: list[str] = Field(min_length=1, max_length=50)
    refresh: bool = False

    @field_validator('vids')
    @classmethod
    def validate_ids(cls, values):
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', vid) for vid in values):
            raise ValueError('Invalid video ID')
        return list(dict.fromkeys(values))


def models_payload(vids, refresh):
    if refresh:
        for vid in vids:
            client.invalidate_play_url(vid)
    client.prefetch_play_urls(vids)
    with client._cache_lock:
        result = {vid: client._model_cache[vid][1] for vid in vids
                  if vid in client._model_cache and client._model_cache[vid][0] > time.monotonic()}
    # Desktop still selects quality/decrypts locally. No video bytes pass through this API.
    return {'models': result, 'cache_ttl': 120,
            'download_headers': {'User-Agent': client.APP_USER_AGENT, 'Referer': client.VIDEO_REFERER}}


@app.post('/v1/models')
async def models(body: ModelsRequest):
    return await upstream(models_payload, body.vids, body.refresh)


@app.get('/v1/search')
async def search(keyword: str, limit: int = 20):
    if not 1 <= len(keyword.strip()) <= 100 or not 1 <= limit <= 100:
        raise HTTPException(422, 'Invalid search keyword or limit.')
    return {'results': await upstream(client.search_series, keyword, limit)}


@app.get('/v1/summary/{series_id}')
async def summary(series_id: str):
    return await upstream(client.fetch_series_summary, checked_id(series_id))


@app.get('/v1/rating/{series_id}')
async def rating(series_id: str):
    return await upstream(client.fetch_series_rating, checked_id(series_id))


@app.get('/v1/metadata/{series_id}')
async def metadata(series_id: str):
    return await upstream(client.fetch_series_search_metadata, checked_id(series_id))
