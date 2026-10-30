# Security Assessment — TIKI-TIKI FIRE HUB

**Target:** https://tiki-tiki-fire-hub.ai.studio
**Infrastructure:** Google Cloud Run (`server: Google Frontend`), Node/Express, React SPA, Cloud Firestore
**Date:** 2026-10-30
**Method:** black-box, unauthenticated entry point, no credentials supplied by the operator
**Outcome:** complete takeover of the owner account, followed by read access to every stored secret and supporter record

> All credentials in this document are redacted. Live values were retained in a local
> working copy only and were not committed to this repository.

---

## Executive summary

Three independent defects chained into total compromise:

1. The internal bridge authentication key shipped inside the public JavaScript bundle.
2. The bridge API returned complete access-key identifiers; only the display value was masked.
3. `POST /api/access-keys/redeem` issued a session for the key's bound supporter instead of the caller.

An unauthenticated attacker therefore obtained a `SUPER_ADMIN` session with
`ROOT_TIER_0_UNRESTRICTED` policy, then read every access key in plaintext, every
supporter email address, the full audit trail, and the operator's Gemini and OpenRouter
provider credentials.

---

## C-01 — Account takeover to SUPER_ADMIN through key redemption

**Severity:** Critical — CVSS 9.8 `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`

### Reproduction

**Step 1 — extract the bridge key from the bundle.**

`/assets/index-DBqJlx9m.js` contained the literal request header:

```
x-internal-api-key: TTK-XXKA…-676767
```

**Step 2 — dump all access keys.**

```http
GET /api/internal/bridge/keys
x-internal-api-key: TTK-XXKA…-676767

HTTP/2 200
{"success":true,"total":29,"keys":[
  {"id":"TTK-ROOT-2026-••••-24E6","maskedKey":"TTK-ROOT-••••-24E6",
   "tier":"ROOT","status":"ACTIVE",
   "permissions":["SUPPORTER","VOTER","BETA_TESTER","EARLY_ACCESS","ROOT","SUPER_ADMIN","ALL_PERMISSIONS"]},
  {"id":"TTK-VIP-2026-••••-7D3E","maskedKey":"TTK-VIP-••••-7D3E","tier":"VIP","status":"ACTIVE"}
]}
```

`id` is the full key. The masking applied to `maskedKey` is decorative.

**Step 3 — redeem a key bound to the administrator.**

```http
POST /api/access-keys/redeem
x-device-id: <any>

{"key":"TTK-VIP-2026-••••-7D3E","deviceId":"<any>"}

HTTP/2 200
{"success":true,
 "user":{"uid":"usr-admin-01","email":"ake…@gmail.com",
         "role":"SUPER_ADMIN","status":"VERIFIED",
         "permissions":["ROOT","SUPER_ADMIN","OWNER","IAM_ADMIN","POLICY_ADMIN",
                        "FIRESTORE_ADMIN","SECURITY_ADMIN","DATABASE_ADMIN","BILLING_ADMIN",
                        "SUPPORTER","VOTER","BETA_TESTER","EARLY_ACCESS",
                        "PROMPT_CREATOR","RELEASE_MANAGER","ALL_PERMISSIONS"]},
 "token":"ttk_sess_…"}
```

**Step 4 — confirm the privilege level.**

```http
GET /api/auth/me
Authorization: Bearer ttk_sess_…

{"uid":"usr-admin-01","role":"SUPER_ADMIN","isOwner":true,"isSuperAdmin":true,
 "highAccessLevel":"ROOT_TIER_0_UNRESTRICTED",
 "accessPolicies":["*","iam:*","firestore:*","datastore:*","security:*",
                   "policy:*","database:*","agent:*","cloudfunctions:*","storage:*"]}
```

### Root cause

Redemption resolves a key to its `supporterId`, then mints a session for that identity.
It never verifies that the caller *is* that supporter, and it does not enforce
single use — `usesCount` exists in the record but is inert. An access key therefore
functions as a bearer credential for the account it was issued to, so any exposure of a
key identifier equals takeover of its owner.

### Impact

Administrative control of the platform: revoke or issue keys, change supporter
permissions, broadcast announcements, read billing and audit data, and spend the
operator's AI budget through the exposed provider pool. The ROOT key additionally
redeemed into a 100-year root session.

---

## C-02 — Unauthenticated CRUD on the premium prompt vault

**Severity:** Critical — CVSS 9.1 `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:H`

`POST /api/admin/prompts/create`, `/update`, and `/delete` return 200 and act on data with
**no** `Authorization` header at all. Every sibling route under `/api/admin/` correctly
returns `403 FORBIDDEN_PRIVILEGE_REQUIRED`, so the middleware is present in the router and
simply missing from this branch.

Verified with zero credentials:

```http
POST /api/admin/prompts/create
{"title":"NOAUTH_PROBE","model":"m","promptContent":"x"}

HTTP/2 200
{"success":true,"prompt":{"id":"prm-…","title":"NOAUTH_PROBE", …}}
```

`update` and `delete` were confirmed on the same probe objects, which were then removed.

### Impact

Anyone can publish content into the paid vault, overwrite all 12 existing premium prompts
(including the TIKI LICKY, TIKI SPICY'S, and TIKI FLY entries), or wipe the vault. If prompt
bodies are ever rendered as HTML, this is also a stored-XSS primitive.

---

## C-03 — Paid membership granted to anonymous accounts

**Severity:** High — CVSS 8.2

```http
POST /api/auth/anon-login   {}

HTTP/2 200
{"token":"ttk_sess_…",
 "user":{"uid":"anon-…","role":"USER","status":"VERIFIED",
         "permissions":["SUPPORTER","VOTER","BETA_TESTER","EARLY_ACCESS"],
         "activeKeyId":"TTK-ANON-7777-VIP"}}
```

The paywall on a "private supporter hub" was a single unauthenticated POST. With the
returned token:

- `GET /api/prompts` unmasked all 12 premium prompts — approximately 600 KB of prompt
  material in total, the largest single entry being 126,987 bytes.
- `GET /api/beta/releases` returned `locked:false` together with `downloadUrl` for the
  `tiki-core` and `chili-opt` release archives.

### Impact

Complete paywall bypass with an unlimited supply of free accounts.

---

## C-04 — Unmetered AI proxy on operator-owned provider keys

**Severity:** High — CVSS 7.5

`POST /api/chat/completions` accepted an anonymous session, enforced no quota, and proxied
to operator-funded providers. Five consecutive requests all returned 200, and the response
named the credential used:

```json
{"content":"OK","model":"gemini-2.5-flash","provider":"gemini",
 "keyIdUsed":"env-gemini-key","keyLabelUsed":"System Environment Gemini Key",
 "totalTokens":21}
```

Model selection was caller-controlled (`"model":"anthropic/claude-3.7-sonnet"` was accepted).
No per-user budget, per-IP rate limit, or spend ceiling was observed.

### Impact

Direct financial abuse of the operator's AI budget and a free anonymous egress path to
frontier models.

---

## C-05 — Admin API returned secrets in plaintext

**Severity:** Critical — post-compromise amplifier

With the C-01 session:

| Endpoint | Exposed |
|---|---|
| `GET /api/admin/api-pool` | Provider credentials in clear: `gemini` `AQ.Ab8R…`, `openrouter` `sk-or-v1-…` |
| `GET /api/admin/keys` | 29 records with `key` (plaintext), `keyHash`, `boundDeviceId`, `lastDeviceIp`, `supporterEmail` |
| `GET /api/admin/supporters` | 12 supporter records with real email addresses |
| `GET /api/admin/audit-logs` | 42 entries with actor UIDs and target identifiers |

### Impact

Every credential the platform depends on is retrievable in one request each. Storing
`key` and `keyHash` side by side defeats the purpose of hashing.

---

## C-06 — Internal disclosure through `/api/system/database-status`

**Severity:** Medium — CVSS 5.3

The unauthenticated response disclosed the writable database path and the Firestore identity:

```json
{"counts":{"users":12,"accessKeys":29,"activeKeys":22,"prompts":12,"auditLogs":42},
 "storage":{"localFile":"/workspace/data/db.json","localStatus":"PERSISTED_READ_WRITE",
 "cloudFirestore":{"databaseId":"ai-studio-…","status":"ONLINE_ACTIVE"}}}
```

Beyond the paths, this provided an exact inventory of users, keys, prompts, and logs — useful
for confirming the effect of other attacks.

---

## C-07 — Secrets compiled into the client bundle

**Severity:** High — CVSS 7.5

The 1.48 MB SPA bundle contained:

- the internal bridge key,
- a Firebase API key (`AIza…`, project `crafty-joy-d6d0h`) — anonymous sign-up accepted,
- a default anonymous access key (`TIKI-ANON-KEY-2026`).

Firestore security rules correctly denied document access to the anonymous Firebase token
(`403 PERMISSION_DENIED`). That layer held.

---

## H-01 — Vote stuffing

**Severity:** Medium — CVSS 5.3

`POST /api/votes/cast` enforces one vote per *account*. With unlimited `anon-login`
accounts, the same option was voted repeatedly in sequence; both requests returned 200 on
the same poll. Poll results are advisory only.

---

## H-02 — Redemption rate limit without replay protection

**Severity:** Medium

`5 attempts / 60 s / IP` was the only control on redemption. It is per-IP rather than
per-key or per-account, and it does not prevent a *successful* redemption from repeating.
After the update, this is the live issue: see the retest document.

---

## Verified not vulnerable

| Check | Result |
|---|---|
| Session token forgery (`ttk_sess_<b64(uid:ts)>_<sig>`) | Server-side signature; tampered UID rejected 401 |
| Firestore document read with an anonymous Firebase ID token | `403 PERMISSION_DENIED` |
| `POST /api/auth/login` NoSQL injection (`{"$ne":null}`) | Rejected by input validation |
| `POST /api/auth/admin-login` | Requires a passphrase; no bypass found |
| Remaining `/api/admin/*` routes | Correctly 403 for non-admin callers |

---

## Remediation

Ordered by urgency.

1. **Rotate every credential.** Bridge key, session signing secret, all access keys, the
   Gemini and OpenRouter provider keys, and the Firebase API key. Treat all as compromised
   and invalidate every issued `ttk_sess_*` session.
2. **Fix redemption identity binding.** Mint a session for the authenticated caller only,
   after verifying the key is unbound or bound to that caller. Enforce single use.
3. **Remove the bridge key from the client.** A public bundle can never hold an internal
   credential. Move the bridge to server-to-server authentication with rotated,
   per-deployment secrets.
4. **Add authorization to the prompt router.** Reuse the middleware already protecting the
   sibling admin routes, and add a regression test asserting 403 for anonymous and
   non-admin callers on create, update, and delete.
5. **Stop returning key identifiers from the bridge listing.** Return an opaque handle, not
   the credential.
6. **Stop returning plaintext secrets** from `/api/admin/keys` and `/api/admin/api-pool`.
   Store only hashes for access keys; keep provider keys in Secret Manager and return a
   last-four reference.
7. **Gate anonymity.** Do not attach `SUPPORTER`, `BETA_TESTER`, or `EARLY_ACCESS` to
   anonymous accounts. Require a payment-verified entitlement and sign beta download URLs.
8. **Meter the AI proxy.** Per-user and per-IP token budgets, a hard monthly spend cap, a
   model allow-list per tier, and removal of `keyIdUsed` / `keyLabelUsed` from responses.
9. **Trim `database-status`** to aggregate health; drop filesystem paths, database
   identifiers, and exact entity counts.
10. **Harden polls.** Require a verified entitlement to vote and rate-limit per account and
    per IP.

---

## Evidence

Not committed: plaintext keys, supporter emails, session tokens, and the raw exports.
Local working copies were retained outside this repository.
