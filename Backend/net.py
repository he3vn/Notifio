"""Shared HTTP plumbing for the scrapers.

Two things every scraper here keeps learning the hard way:

* endpoints flake: YouTube's RSS feed randomly answers 404 to anonymous
  pollers, requests time out, connections die mid-body. Retrying a few
  times with a short backoff makes those errors disappear.
* fetching one channel at a time is the real speed killer. A small
  thread pool fans the work out without new dependencies.
"""
import gzip
import random
import ssl
import threading
import time
import urllib.error
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"

# Status codes that mean "ask again", not "gone".
FLAKY = frozenset((408, 425, 429, 500, 502, 503, 504))


def ssl_context():
    """CA bundle via certifi when available, Python's default otherwise."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


_SSL_CONTEXT = None
_SSL_LOCK = threading.Lock()


def _ssl_ctx():
    global _SSL_CONTEXT
    with _SSL_LOCK:
        if _SSL_CONTEXT is None:
            _SSL_CONTEXT = ssl_context()
        return _SSL_CONTEXT


def gunzip(raw):
    """Decompress a gzip body; salvage the readable prefix if truncated."""
    if raw[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(raw)
        except Exception:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            try:
                return d.decompress(raw)
            except Exception:
                return raw
    return raw


def http_get(url, headers=None, timeout=8, tries=3, backoff=0.25,
             retry=FLAKY, limit=None):
    """GET with retries and gzip support. Returns (status, headers, body).

    Retries while the status code is in `retry` (default: the usual
    "try me again" codes) or the request dies on the network. 404 is
    NOT retried by default - pass retry=FLAKY | {404} for endpoints
    known to flake that way (YouTube feeds).
    """
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    for attempt in range(tries):
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=_ssl_ctx()) as r:
                body = gunzip(r.read(limit) if limit else r.read())
                return r.status, r.headers, body
        except urllib.error.HTTPError as e:
            if e.code not in retry or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == tries - 1:
                raise
        time.sleep(backoff * (2 ** attempt) + random.random() * 0.15)
    raise AssertionError("unreachable")


def get_text(url, limit=None, **kw):
    _, _, body = http_get(url, limit=limit, **kw)
    return body.decode("utf-8", "ignore")


def run_parallel(fn, items, workers=8):
    """Run fn over items in a small thread pool.

    Returns [(item, result, error)] in input order with exactly one of
    result/error set - errors never escape, the caller decides what to
    do with them.
    """
    items = list(items)
    if not items:
        return []
    out = []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
        futures = [(it, ex.submit(fn, it)) for it in items]
        for it, fut in futures:
            try:
                out.append((it, fut.result(), None))
            except Exception as e:
                out.append((it, None, e))
    return out
