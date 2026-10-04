"""Client for the Hongguo/Fanqie app APIs used by public drama pages."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from hq_service import signer


API_BASE_URL = "https://api5-normal-sinfonlineb.fqnovel.com"
WEB_BASE_URL = "https://hongguoduanju.com"
APP_USER_AGENT = (
    "com.phoenix.read/72232 (Linux; U; Android 9; SM-N9860; "
    "Build/PQ3A.190705.10241111;tt-ok/3.12.13.20)"
)
WEB_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 9; SM-N9860) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/88.0.4324.152 Mobile Safari/537.36"
)
SEARCH_WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIDEO_REFERER = "https://novelquickapp.com/"

COMMON_QUERY = {
    "ac": "wifi",
    "channel": "oppo_8662_64",
    "aid": "8662",
    "app_name": "novelread",
    "version_code": "72232",
    "version_name": "7.2.2.32",
    "device_platform": "android",
    "os": "android",
    "ssmix": "a",
    "device_type": "SM-N9860",
    "device_brand": "Samsung",
    "language": "zh",
    "os_api": "28",
    "os_version": "9",
    "manifest_version_code": "72232",
    "resolution": "900*1600",
    "dpi": "320",
    "update_version_code": "72232",
    "host_abi": "arm64-v8a",
    "compliance_status": "0",
    "need_personal_recommend": "1",
    "player_so_load": "1",
    "is_android_pad_screen": "0",
    "rom_version": "PQ3A.190705.10241111+release-keys",
}
HEADERS = {
    "User-Agent": APP_USER_AGENT,
    "Accept-Encoding": "gzip",
    "Accept": "application/json",
    "Content-Type": "application/json; charset=utf-8",
}
DETAIL_BIZ_PARAM = {
    "detail_page_version": 0,
    "disable_digg_stat": False,
    "image_shrink_datas_str": (
        "W3siaW1hZ2VfdHlwZSI6MywiaW1hZ2Vfd2lkdGgiOjkwMCwic2hyaW5rX3R5cGUiOjN9LHsi"
        "aW1hZ2VfdHlwZSI6NCwiaW1hZ2Vfd2lkdGgiOjcyLCJzaHJpbmtfdHlwZSI6NH1d\n"
    ),
    "need_all_video_definition": False,
    "need_mp4_align": False,
    "screen_width_px": "900",
    "source": 7,
    "use_os_player": False,
    "use_server_dns": False,
}
MODEL_BIZ_PARAM = {
    "detail_page_version": 0,
    "device_level": 3,
    "disable_digg_stat": False,
    "need_all_video_definition": True,
    "need_mp4_align": False,
    "use_os_player": False,
    "use_server_dns": False,
    "video_platform": 1024,
}

DETAIL_ENDPOINT = '/novel/player/multi_video_detail/v1/'
MODEL_ENDPOINT = '/novel/player/multi_video_model/v1/'
_api_lock = threading.Lock()
_identity_lock = threading.Lock()
_identity: dict | None = None
_last_request = 0.0
_model_cache: dict[str, tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


class AccessDeniedError(RuntimeError):
    """Authentication, captcha or rate limits: do not rotate guest identities."""


def _guest_identity() -> dict:
    global _identity
    with _identity_lock:
        if _identity is not None:
            return dict(_identity)
        configured = {k: os.getenv(env, '').strip() for k, env in
                      [('device_id', 'HQ_DEVICE_ID'), ('iid', 'HQ_IID'), ('cdid', 'HQ_CDID')]}
        if any(configured.values()):
            if (not all(configured[k].isdigit() and 15 <= len(configured[k]) <= 19
                        for k in ('device_id', 'iid')) or not configured['cdid']):
                raise RuntimeError('Configure HQ_DEVICE_ID, HQ_IID and HQ_CDID together.')
            uuid.UUID(configured['cdid'])
            _identity = configured
            return dict(_identity)
        path = Path(os.getenv('HONGGUO_DEVICE_FILE', '') or
                    Path(os.getenv('HQ_DATA_DIR', './data')) / 'hongguo-device.json')
        try:
            candidate = json.loads(path.read_text(encoding='utf-8'))
            if (not all(str(candidate.get(k, '')).isdigit() for k in ('device_id', 'iid'))
                    or not 15 <= len(str(candidate['device_id'])) <= 19
                    or not 15 <= len(str(candidate['iid'])) <= 19):
                raise ValueError('invalid guest ID')
            uuid.UUID(candidate['cdid'])
            _identity = {k: str(candidate[k]) for k in ('device_id', 'iid', 'cdid')}
        except FileNotFoundError:
            _identity = {'device_id': str(10**15 + uuid.uuid4().int % (9 * 10**15)),
                         'iid': str(10**15 + uuid.uuid4().int % (9 * 10**15)), 'cdid': str(uuid.uuid4())}
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation prevents overwriting another backend's identity.
            try:
                with path.open('x', encoding='utf-8') as output:
                    json.dump(_identity, output)
            except FileExistsError:
                _identity = None
                candidate = json.loads(path.read_text(encoding='utf-8'))
                uuid.UUID(candidate['cdid'])
                _identity = {k: str(candidate[k]) for k in ('device_id', 'iid', 'cdid')}
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError('Cấu hình khách Hongquo hỏng. Kiểm tra data/hongguo-device.json; không tự xoay ID để né giới hạn.') from exc
        return dict(_identity)


def _fetch_web_text(url: str, *, max_bytes: int = 8_000_000) -> str:
    """Fetch a public Hongquo page without starting a browser."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEARCH_WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(max_bytes)
        headers = getattr(response, "headers", None)
        charset = headers.get_content_charset() if headers and hasattr(headers, "get_content_charset") else None
    return raw.decode(charset or "utf-8", "replace")


def _extract_router_data(html: str) -> dict:
    """Read the SSR JSON embedded in Hongquo's modern-router script."""
    match = re.search(
        r"<script\b[^>]*data-script-src\s*=\s*['\"]modern-inline['\"][^>]*>(.*?)</script\s*>",
        str(html or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("Hongquo không tìm thấy dữ liệu SSR của trang.")
    script = match.group(1)
    marker = re.search(r"_ROUTER_DATA\s*=\s*", script)
    if not marker:
        raise RuntimeError("Hongquo không tìm thấy router data của trang.")
    try:
        payload, _ = json.JSONDecoder().raw_decode(script[marker.end():])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Dữ liệu SSR Hongquo không hợp lệ.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Dữ liệu SSR Hongquo không đúng cấu trúc.")
    return payload


def _loader_route(router_data: dict, route_name: str) -> dict:
    loader_data = router_data.get("loaderData") if isinstance(router_data, dict) else None
    if not isinstance(loader_data, dict):
        return {}
    direct = loader_data.get(route_name)
    if isinstance(direct, dict):
        return direct
    for key, value in loader_data.items():
        if str(key).replace("\\u002F", "/") == route_name and isinstance(value, dict):
            return value
    return {}


def search_series(keyword: str, max_items: int = 20) -> list[dict]:
    """Search Hongquo's public web index through a plain HTTP request.

    The search route server-renders ``searchList`` into its router JSON.  It
    is intentionally parsed here instead of using a browser or Playwright.
    """
    cleaned_keyword = str(keyword or "").strip()
    if not cleaned_keyword:
        raise ValueError("Hongquo search cần từ khóa.")
    requested_limit = max(1, min(int(max_items or 1), 100))
    encoded_keyword = urllib.parse.quote(cleaned_keyword, safe="")
    html = _fetch_web_text(f"{WEB_BASE_URL}/search/{encoded_keyword}")
    route = _loader_route(_extract_router_data(html), "search_(keyword)/page")
    rows = route.get("searchList")
    if not isinstance(rows, list):
        raise RuntimeError("Hongquo không trả về danh sách searchList.")
    return [row for row in rows if isinstance(row, dict)][:requested_limit]


def _fetch_series_video_data(series_id: str) -> dict:
    payload = api_call(
        DETAIL_ENDPOINT,
        {"biz_param": DETAIL_BIZ_PARAM, "series_id": str(series_id)},
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"Hongquo detail API error: {json.dumps(payload, ensure_ascii=False)[:200]}")
    data = payload.get("data") or {}
    resolved_id = str(series_id)
    entry = data.get(resolved_id)
    if not isinstance(entry, dict):
        entry = next((value for value in data.values() if isinstance(value, dict)), None)
    video_data = entry.get("video_data") if isinstance(entry, dict) else None
    if not isinstance(video_data, dict):
        raise RuntimeError("Hongquo không trả dữ liệu series.")
    return video_data


def fetch_series_summary(series_id: str) -> dict:
    """Return series counters through the signed guest API."""
    video_data = _fetch_series_video_data(str(series_id))
    return {
        "title": video_data.get("series_title") or "",
        "thumbnail": video_data.get("series_cover") or video_data.get("cover_url") or "",
        "episodes": video_data.get("episode_cnt"),
        "views": video_data.get("series_play_cnt") or video_data.get("play_cnt"),
        "hot_score": video_data.get("hot_score"),
    }


def _rating_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 10:
        return None
    return number


def fetch_series_rating(series_id: str) -> dict:
    """Calculate the displayed 10-point score from public detail reviews."""
    encoded_id = urllib.parse.quote(str(series_id), safe="")
    html = _fetch_web_text(f"{WEB_BASE_URL}/detail?series_id={encoded_id}")
    route = _loader_route(_extract_router_data(html), "detail_page")
    social_info = route.get("seriesSocialInfo") if isinstance(route, dict) else None
    if not isinstance(social_info, dict):
        return {}
    direct_rating = social_info.get("rating") or social_info.get("average_rating")
    if direct_rating not in (None, ""):
        rating = _rating_number(direct_rating)
        if rating is not None:
            return {"rating": round(rating, 1)}
    reviews = social_info.get("reviews")
    review_rows = reviews.get("reviews") if isinstance(reviews, dict) else None
    values = [
        rating
        for row in (review_rows if isinstance(review_rows, list) else [])
        if isinstance(row, dict)
        if (rating := _rating_number(row.get("rating"))) is not None
    ]
    if not values:
        return {}
    return {"rating": round(sum(values) / len(values), 1)}


def fetch_series_search_metadata(series_id: str) -> dict:
    """Best-effort HTTP enrichment used by keyword search cards."""
    metadata: dict = {}
    for fetcher in (fetch_series_summary, fetch_series_rating):
        try:
            candidate = fetcher(str(series_id))
        except Exception:  # noqa: BLE001 - one missing counter must not drop a result
            continue
        if isinstance(candidate, dict):
            metadata.update({key: value for key, value in candidate.items() if value not in (None, "")})
    return metadata


def api_call(path: str, body: dict, retries: int = 3) -> dict:
    global _last_request
    data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with _api_lock:
                delay = .75 - (time.monotonic() - _last_request)
                if delay > 0:
                    time.sleep(delay)
                query = {**COMMON_QUERY, **_guest_identity(), '_rticket': str(int(time.time() * 1000))}
                base = os.getenv('HONGGUO_API_BASE_URL', '') or API_BASE_URL
                if urllib.parse.urlsplit(base).scheme != 'https':
                    raise ValueError('Hongquo API phải dùng HTTPS')
                url = f"{base.rstrip('/')}{path}?{urllib.parse.urlencode(query)}"
                headers = {**HEADERS, 'x-ss-stub': hashlib.md5(data).hexdigest().upper()}
                headers.update(signer.sign(url, headers))
                _last_request = time.monotonic()
                request = urllib.request.Request(url, data=data, headers=headers, method='POST')
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read(8_000_001)
                    if response.headers.get('Content-Encoding') == 'gzip':
                        raw = gzip.decompress(raw)
                    if not raw:
                        raise RuntimeError('HTTP 200 nhưng body rỗng: kiểm tra chữ ký, thời gian và chính sách API Hongquo.')
                    if len(raw) > 8_000_000:
                        raise RuntimeError('Hongquo API trả dữ liệu quá lớn.')
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise RuntimeError('Hongquo API trả JSON sai cấu trúc.')
                    code = payload.get('code')
                    if code not in (0, None):
                        raise AccessDeniedError(f'Hongquo API từ chối yêu cầu (code={code}). Có thể cần đăng nhập/xác minh hợp lệ hoặc chờ hết giới hạn; xem docs/hongguo-download.md.')
                    return payload
        except (AccessDeniedError, signer.SignerError):
            raise
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 429):
                raise AccessDeniedError(f'Hongquo HTTP {exc.code}: cần quyền truy cập hợp lệ hoặc chờ hết giới hạn. Không xoay ID thiết bị.') from exc
            last_error = RuntimeError(f'HTTP {exc.code}')
        except Exception as exc:  # noqa: BLE001 - retries wrap network/parser failures
            last_error = exc
        if attempt + 1 < max(1, retries):
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Hongquo API {path} failed: {last_error}")


def resolve_series_id(value: str) -> str:
    target = str(value or "").strip()
    if re.fullmatch(r"\d{15,25}", target):
        return target
    match = re.search(r"[?&]series_id=(\d+)", target) or re.search(r"/player/(\d+)", target)
    if match:
        return match.group(1)
    if not target.startswith(("http://", "https://")):
        raise RuntimeError("Link Hongquo không hợp lệ hoặc thiếu series_id.")

    request = urllib.request.Request(target, headers={"User-Agent": WEB_USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read(2_000_000).decode("utf-8", "replace")
        final_url = response.url
    match = re.search(r"video_series_id=(\d+)", final_url) or re.search(r"video_series_id=(\d+)", text)
    if not match:
        match = re.search(r'"video_id"\s*:\s*"(\d+)"', text)
    if not match:
        raise RuntimeError(f"Không tìm thấy series_id trong link Hongquo: {target}")
    return match.group(1)


def fetch_episode_list(series_id: str) -> dict:
    payload = api_call(
        DETAIL_ENDPOINT,
        {"biz_param": DETAIL_BIZ_PARAM, "series_id": series_id},
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"Hongquo detail API error: {json.dumps(payload, ensure_ascii=False)[:200]}")
    data = payload.get("data") or {}
    resolved_id = str(series_id) if str(series_id) in data else next(iter(data), None)
    if not resolved_id:
        raise RuntimeError("Hongquo không trả dữ liệu series.")
    video_data = data[resolved_id].get("video_data") or {}
    episodes = [
        {
            "vid": str(item["vid"]),
            "index": int(item.get("vid_index") or 0),
            "title": item.get("title") or "",
            "duration": item.get("duration"),
        }
        for item in video_data.get("video_list") or []
        if item.get("vid")
    ]
    episodes.sort(key=lambda episode: episode["index"])
    if not episodes:
        raise RuntimeError('Hongquo không trả danh sách tập. Không thể coi một series rỗng là tải thành công.')
    count = int(video_data.get('episode_cnt') or len(episodes))
    if count != len(episodes) or {e['index'] for e in episodes} != set(range(1, count + 1)) or len({e['vid'] for e in episodes}) != count:
        raise RuntimeError(f'Hongquo danh sách tập thiếu/trùng: nhận {len(episodes)}/{count}. Không thể xác nhận tải full; kiểm tra quyền/API thay vì coi partial là thành công.')
    return {
        "series_id": str(resolved_id),
        "title": video_data.get("series_title") or "Phim ngắn Hongquo",
        "cover": video_data.get("series_cover") or video_data.get("cover_url") or "",
        "episodes": episodes,
        "episode_count": count,
    }


def prefetch_play_urls(vids: list[str]) -> None:
    """Fetch five episodes per signed request; cache stream models for ten minutes."""
    pending = []
    with _cache_lock:
        for vid in dict.fromkeys(map(str, vids)):
            cached = _model_cache.get(vid)
            if cached is None or cached[0] <= time.monotonic():
                _model_cache.pop(vid, None)
                pending.append(vid)
    for start in range(0, len(pending), 5):
        payload = api_call(MODEL_ENDPOINT, {'biz_param': MODEL_BIZ_PARAM,
                          'mixed_video_id_map': {'1': pending[start:start + 5]}})
        for vid, item in (payload.get('data') or {}).items():
            model = item.get('video_model') if isinstance(item, dict) else None
            model = json.loads(model) if isinstance(model, str) else model
            tracks = [s for s in (model or {}).get('video_list', []) if s.get('main_url')]
            if tracks:
                with _cache_lock:
                    _model_cache[str(vid)] = (time.monotonic() + 600, tracks)


def invalidate_play_url(vid: str) -> None:
    with _cache_lock:
        _model_cache.pop(str(vid), None)


def fetch_play_url(vid: str, quality: str = "best") -> tuple[str, str | None]:
    prefetch_play_urls([vid])
    with _cache_lock:
        cached = _model_cache.get(str(vid))
        candidates = cached[1] if cached and cached[0] > time.monotonic() else []
    if not candidates:
        return "", None

    def codec(stream: dict) -> str:
        return str((stream.get("video_meta") or {}).get("codec_type") or stream.get('codec_type') or "").lower()

    def definition(stream: dict) -> int:
        match = re.search(r"(\d+)", str((stream.get("video_meta") or {}).get("definition") or ""))
        return int(match.group(1)) if match else 0

    def bitrate(stream: dict) -> int:
        metadata = stream.get("video_meta") or {}
        return int(metadata.get("bitrate") or metadata.get("real_bitrate") or 0)

    playable = [stream for stream in candidates if codec(stream) != "bytevc2"]
    if not playable:
        raise RuntimeError('Hongquo chỉ trả codec bytevc2 chưa được hỗ trợ; không lưu file không xem được.')
    if quality == "best":
        selected = max(playable, key=lambda stream: (definition(stream), bitrate(stream)))
    elif quality == "worst":
        selected = min(playable, key=lambda stream: (definition(stream), -bitrate(stream)))
    else:
        match = re.fullmatch(r"(\d+)p?", str(quality or "").strip().lower())
        if not match:
            raise ValueError(f"Chất lượng Hongquo không hợp lệ: {quality}")
        target = int(match.group(1))
        lower = [stream for stream in playable if definition(stream) <= target]
        selected = max(lower, key=lambda stream: (definition(stream), bitrate(stream))) if lower else min(playable, key=definition)
    encrypt_info = selected.get("encrypt_info") or {}
    if encrypt_info.get('encrypt') and not encrypt_info.get('spade_a'):
        raise RuntimeError('Hongquo trả video mã hóa nhưng thiếu spade_a; không thể tải thành MP4 hợp lệ.')
    return selected["main_url"], encrypt_info.get("spade_a") or None
