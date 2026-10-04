"""Owned, loopback-only Java/unidbg signer; no Android app or paid service."""
from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_process: subprocess.Popen | None = None
_url = ''
_SIGNATURE_HEADERS = {'x-argus', 'x-gorgon', 'x-khronos', 'x-ladon', 'x-helios', 'x-medusa', 'x-neptune', 'x-soter'}


class SignerError(RuntimeError):
    pass


def _java() -> str:
    explicit = os.getenv('HONGGUO_JAVA', '').strip()
    candidates = [explicit] if explicit else [
        str(Path(os.getenv('JAVA_HOME', '')) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')),
        shutil.which('java') or '',
        r'C:\Program Files\Android\Android Studio\jbr\bin\java.exe',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SignerError('Hongquo cần Java 17+ để ký API. Cài Java hoặc đặt HONGGUO_JAVA tới java.exe; xem docs/hongguo-download.md.')


def _loopback_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {'', '/', '/sign'}):
        raise SignerError('HONGGUO_SIGN_SERVER chỉ chấp nhận HTTP loopback, ví dụ http://127.0.0.1:19099.')
    return value.rstrip('/') if parsed.path == '/sign' else value.rstrip('/') + '/sign'


def _ensure_server() -> str:
    global _process, _url
    configured = os.getenv('HONGGUO_SIGN_SERVER', '').strip()
    if configured:
        return _loopback_url(configured)
    if _process is not None and _process.poll() is None:
        return _url
    assets = Path(os.getenv('HONGGUO_SIGNER_DIR', '') or Path(__file__).parent / 'assets').resolve()
    required = [assets / 'sign' / 'unidbg-sign.jar',
                *[assets / 'capture' / 'fq_oversea' / name for name in
                  ('libmetasec_ml.so', 'libc++_shared.so', 'ms_16777218.bin')]]
    if any(not p.is_file() for p in required):
        raise SignerError('Thiếu tài nguyên bộ ký Hongquo trong backend/services/hongguo/assets. Khôi phục cả JAR, hai SO và chứng thư; xem docs/hongguo-download.md.')
    try:
        manifest = json.loads((assets / 'manifest.json').read_text(encoding='utf-8'))
        for path in required:
            expected = manifest['sha256'][path.relative_to(assets).as_posix()]
            if hashlib.sha256(path.read_bytes()).hexdigest().lower() != expected.lower():
                raise ValueError('asset hash mismatch')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SignerError('Tài nguyên ký Hongquo bị thay đổi/hỏng hoặc thiếu manifest.json. Chỉ cập nhật cả bộ từ nguồn đáng tin, kèm checksum đúng.') from exc
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    _url = f'http://127.0.0.1:{port}/sign'
    _process = subprocess.Popen(
        [_java(), '--add-opens', 'java.base/java.lang=ALL-UNNAMED', '-Xmx384m',
         '-cp', 'unidbg-sign.jar', 'com.hongguo.sign.FqTrace', 'serve', str(port)],
        cwd=assets / 'sign', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _process.poll() is not None:
            code = _process.returncode
            close()
            raise SignerError(f'Bộ ký Hongquo dừng khi khởi động (exit={code}). Kiểm tra Java 17+, thư viện SO và chứng thư đi kèm.')
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                logger.info('Hongquo local signer started (port=%s)', port)
                return _url
        except OSError:
            time.sleep(.15)
    close()
    raise SignerError('Bộ ký Hongquo không khởi động trong 30 giây. Kiểm tra Java và bộ tài nguyên ký.')


def sign(url: str, headers: dict) -> dict:
    """Sign the exact URL/headers; serialize access to the native emulator."""
    with _lock:
        endpoint = _ensure_server()
        request = urllib.request.Request(endpoint,
            data=json.dumps({'url': url, 'headers': headers}, separators=(',', ':')).encode(),
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            # No environment proxy for a request carrying local signing inputs.
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=45) as response:
                raw = response.read(65_537)
            if len(raw) > 65_536:
                raise ValueError('oversized signer response')
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get('error'):
                raise ValueError('signer error')
            result = {k: v for k, v in payload.items() if k.lower() in _SIGNATURE_HEADERS
                      and isinstance(v, str) and v and '\r' not in v and '\n' not in v}
            if not {'x-argus', 'x-gorgon', 'x-khronos'} <= {k.lower() for k in result}:
                raise ValueError('missing signature headers')
            return result
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise SignerError('Không tạo được chữ ký Hongquo. Kiểm tra dịch vụ Java; không thể thay bằng ID điện thoại mới.') from exc


def close() -> None:
    """Stop only the process created by this module, never an external signer."""
    global _process, _url
    with _lock:
        process, _process = _process, None
        _url = ''
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


atexit.register(close)
