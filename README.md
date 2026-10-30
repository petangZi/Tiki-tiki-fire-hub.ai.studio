# TIKI-TIKI FIRE HUB — Security & UI Assessment

Assessments of https://tiki-tiki-fire-hub.ai.studio — a private supporter community hub
(Express on Google Cloud Run, React SPA, Firestore) selling access keys, premium prompt
packs, and AI chat access.

## Index

| Document | Scope |
|---|---|
| [security/assessment-2026-10-30.md](security/assessment-2026-10-30.md) | Full black-box assessment: results of the first pass, chain of compromise, remediation |
| [security/recheck-2026-10-30.md](security/recheck-2026-10-30.md) | Retest after the update: what is fixed, what is still live, measured evidence |
| [ui/critique.md](ui/critique.md) | Interface critique: typography, navigation, accessibility, state design, design-token debt |
| [poc/poc_chain.py](poc/poc_chain.py) | Reproducer for the assessment (no credentials embedded) |
| [artifacts/](artifacts) | Rendered screenshots and DOM audit dumps |

## Status at a glance

| ID | Finding | First pass | After update |
|---|---|---|---|
| C-01 | Account takeover to SUPER_ADMIN via access-key redemption | Critical | **Fixed** — redemption now binds to the caller |
| C-02 | Unauthenticated CRUD on the admin prompt vault | Critical | **Fixed** — 403 on all three routes |
| C-03 | Paid tier granted to anonymous accounts | High | **Fixed** — guests get no permissions |
| C-04 | Unmetered AI proxy on operator-owned provider keys | High | **Fixed** — membership required |
| C-05 | Admin API returned provider keys and access keys in plaintext | Critical | Not re-testable without admin access; rotate instead |
| C-06 | Internal path and Firestore database ID disclosure | Medium | **Fixed** — response trimmed |
| C-07 | Secrets compiled into the public SPA bundle | High | **Fixed** — placeholder shipped, bridge key revoked |
| H-01 | Vote stuffing via unlimited anonymous accounts | Medium | Open |
| H-02 | Access keys not rotated after disclosure | Medium | **Open** — leaked keys still redeem |

## Headline

The authorization bugs that allowed full administrative takeover are closed, and the
bridge credential was revoked and removed from the client bundle. The remaining live
exposure is credential rotation: access keys disclosed during the first pass still
redeem successfully and grant paid membership to anyone holding them.

The interface is competent and visually distinctive but carries structural debt: navigation
is not routable, the type system is not actually rendering the fonts it loads, and gated
content is presented as empty content.

---

Generated 2026-10-30. Secrets in these documents are redacted; working copies were not
committed.
