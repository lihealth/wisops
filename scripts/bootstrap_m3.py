# -*- coding: utf-8 -*-
"""
一键执行 M3 图谱补全：Schema → Category + CLASSIFIED_AS → TRIGGERS。

前置：graph-api 已启动且可连 HugeGraph。

  python scripts/bootstrap_m3.py
  python scripts/bootstrap_m3.py --api http://localhost:8002 --top-k 2
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _post_json(url: str, body: bytes = b"{}") -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode())


def _post_empty(url: str) -> dict:
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser(description="M3 bootstrap: schema, categories, triggers")
    ap.add_argument("--api", default="http://localhost:8002", help="graph-api base URL")
    ap.add_argument("--top-k", type=int, default=2, dest="top_k", help="top_k_per_alert (1–5)")
    ap.add_argument(
        "--vectors",
        action="store_true",
        help="结束后尝试 POST /admin/fault-vectors/sync（需配置 EMBEDDING 或 LLM 密钥）",
    )
    args = ap.parse_args()
    base = args.api.rstrip("/")
    top_k = max(1, min(int(args.top_k), 5))

    steps = [
        ("POST", f"{base}/admin/schema/init", _post_json),
        ("POST", f"{base}/admin/categories/init", _post_json),
    ]
    for method, url, fn in steps:
        print(f"{method} {url}", flush=True)
        try:
            out = fn(url)
            print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            print(f"HTTP {e.code}: {body}", file=sys.stderr, flush=True)
            return 1
        except urllib.error.URLError as e:
            print(str(e), file=sys.stderr, flush=True)
            return 1

    sync_url = f"{base}/admin/triggers/sync?top_k_per_alert={top_k}"
    print(f"POST {sync_url}", flush=True)
    try:
        out = _post_empty(sync_url)
        print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"HTTP {e.code}: {body}", file=sys.stderr, flush=True)
        return 1
    except urllib.error.URLError as e:
        print(str(e), file=sys.stderr, flush=True)
        return 1

    if args.vectors:
        vurl = f"{base}/admin/fault-vectors/sync"
        print(f"POST {vurl}", flush=True)
        try:
            out = _post_empty(vurl)
            print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            print(f"[vectors] HTTP {e.code}: {body}", file=sys.stderr, flush=True)
        except urllib.error.URLError as e:
            print(f"[vectors] {e}", file=sys.stderr, flush=True)

    print("\n建议随后执行: Invoke-RestMethod {0}/ops/stats".format(base), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
