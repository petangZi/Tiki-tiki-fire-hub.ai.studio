# Interface Critique — TIKI-TIKI FIRE HUB

**URL:** https://tiki-tiki-fire-hub.ai.studio
**Build:** `assets/index-_dL3eGSa.js`, `assets/index-MZqB_nAc.css`
**Date:** 2026-10-30
**Method:** headless Chromium against the deployed build. Two viewports — 1440×757 desktop,
390×844 mobile with device emulation. Measured: computed styles, contrast ratios (WCAG AA),
tap-target geometry, accessible names, heading order, landmark structure, horizontal
overflow, font resolution, and per-view state after navigating all five sections.

Raw measurements: [`../artifacts/views-audit.json`](../artifacts/views-audit.json),
[`../artifacts/screenshots-dom-audit.json`](../artifacts/screenshots-dom-audit.json).
Screenshots: [`../artifacts/screenshots/`](../artifacts/screenshots).

---

## Verdict

The visual direction is coherent and clearly deliberate: near-black `#06070a` ground,
crimson primary, glass surfaces, mono micro-labels, heavy geometric sans headings. It reads
as a private, slightly dangerous tool — which is the right register for the product.

The problems are structural, not decorative. The app does not render the typefaces it loads,
it does not have routes, it presents gated content as empty content, and its design tokens
are applied inconsistently enough that the system drifts between screens. Those four issues
are what make it feel less finished than it is.

Contrast is genuinely good — zero WCAG AA failures across five views and both viewports.
That is uncommon and worth preserving rather than redesigning around.

---

## What works

- **Palette direction.** Near-black with a crimson primary is right for the product and does
  not read as a template. The measured text contrast passes AA everywhere tested.
- **Hieroglyphic restraint on data.** The fact that most labels are mono, small, and
  letterspaced gives the dense key/tier data a machine-shop feel that suits the subject.
- **Information architecture.** The sidebar grouping — `PLATFORM UTAMA`, `KOMUNITAS`,
  `AKUN & PROFIL` — is a sensible model for the product's five sections.
- **No layout breakage.** Zero horizontal overflow at 390 px; the off-canvas sidebar
  (`x: -288`) correctly stays closed on mobile.

---

## Findings

### 1. The type system is not rendering — high impact

The document loads Plus Jakarta Sans and JetBrains Mono from Google Fonts, then renders in
system fonts.

Measured across the rendered page:

| Family resolved | Elements |
|---|---|
| `-apple-system` / system sans | 102 |
| `ui-monospace` (fallback) | 18 |
| `Plus Jakarta Sans` | 2 |

`document.fonts.check('600 16px "Plus Jakarta Sans"')` → `true`, but only two elements
resolve to it. `document.fonts.check('500 12px "JetBrains Mono"')` → `false`: the mono face
never loads at all, while 18 elements ask for mono.

Consequence: the identity you designed in Figma or on a Mac is not what most users see.
Headings fall back to whichever grotesque the OS ships — Segoe UI on Windows, Roboto on
Android, Liberation Sans on Linux — so letter widths, weight, and rhythm drift per platform.
The two webfont requests are pure cost with no payoff.

**Fix.** Load both faces once, self-hosted, with `font-display: swap` and a preload for the
single heading weight you actually use. Then bind them through tokens instead of utilities:

```css
@font-face {
  font-family: "Jakarta";
  src: url("/fonts/jakarta-var.woff2") format("woff2-variations");
  font-weight: 200 800;
  font-display: swap;
}
:root {
  --font-sans: "Jakarta", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
body { font-family: var(--font-sans); }
```

Then delete `font-mono`/`font-sans` utility usage in favour of the two variables. If you
decide the mono face is not worth 40 KB, drop JetBrains Mono from the `<link>` entirely —
right now you are paying for a request that resolves to `ui-monospace` anyway.

---

### 2. Nothing is routable — high impact

Across all five views, `location.hash` stays empty and the page contains **zero `<a href>`
elements**. Navigation is 100% `<button>` state changes.

Consequences that users feel directly:

- Back and forward do nothing. Browser back exits the app.
- No view can be linked, shared, or bookmarked. "Look at this prompt" requires instructions.
- Reload always returns to the landing view.
- Opening a prompt from a search result, an email, or a chat message is impossible.
- The accessibility tree exposes no `navigation` landmark, so screen-reader users cannot
  jump to or enumerate the menu. Measured: `nav: 0`, `main: 1`, `footer: 0`.

**Fix.** Route each section. React Router or a 40-line hash router both work; the only
requirement is that the URL changes and the state survives reload.

```jsx
<nav aria-label="Bagian utama">
  <NavLink to="/vault" aria-current={isActive ? "page" : undefined}>Tiki Vault</NavLink>
</nav>
```

`aria-current="page"` also replaces the hand-rolled active styling, which currently depends
on a boolean passed down to each row.

---

### 3. Gated content is rendered as empty content — high impact

On the Voting view the page states both of these at once:

> 🔐 **Hanya Supporter Terverifikasi yang dapat memilih**
> **Belum Ada Polling Aktif**

The API returns three open polls. The second message is false: polls exist, the viewer simply
cannot see them. A user reading that concludes the community is dead, not that they need to
upgrade. This is the single most costly message in the product, because it sits exactly where
conversion should happen.

Beta Lab does the same thing — the gate banner and the release cards render together, so the
page simultaneously says "you cannot be here" and shows the content.

**Fix.** Separate the two states in the component model, not in conditional wording:

```jsx
{canVote ? <PollList polls={polls} />
         : <UpgradeGate reason="voting" pollCount={polls.length} />}
```

`UpgradeGate` should show what is behind the wall — "3 poll aktif, hasil terlihat setelah
aktivasi" — instead of an empty-state illustration. An empty state is for zero data. A gate
is for data the viewer cannot reach. They should never be the same component.

---

### 4. Bootstrap sequence costs the first impression — medium impact

The landing view renders an overlay:

> Menghubungkan ke Cloud Firestore Database
> CONNECTING… 29%
> [ Lewati Transisi ]

Three problems in four lines:

- **It leaks infrastructure vocabulary to end users.** "Cloud Firestore Database" is a
  backend detail, and it is the first sentence the product says about itself.
- **The percentage is not connected to work.** It advances on a timer; there is nothing to
  measure. Users learn that the meter lies.
- **It delays the product.** First `h1` paints at 2.38 s. The skip control is 34 px tall —
  below the 44 px touch minimum — so the escape hatch is itself a small-target violation.

**Fix.** Replace with a shell that paints immediately: sidebar, header, and skeleton cards in
under 200 ms. If a warm-up really is required, say something true and product-shaped —
"Memuat vault" — and never show a number you cannot compute.

---

### 5. Tap targets sit below the minimum — medium impact

Measured controls smaller than 44×44 px:

| Viewport | Count |
|---|---|
| 1440×900 | 27 |
| 390×844 | 31 |

Breakdown: sidebar rows 32–35 px tall, header icon buttons 28–36 px, footer-ish rows 28–30 px,
search and inbox 36×36, one 28×28 icon button with no accessible name on mobile.

WCAG 2.5.8 asks for 24×24 minimum and 2.5.5 recommends 44×44. The sidebar rows are 259 px
wide, so the fix costs nothing visually — grow the row height, not the padding.

**Fix.** `min-height: 44px` on nav rows and icon buttons; `padding-block: 10px` on the 28 px
rows. Give the unlabeled icon button `aria-label="Kirim"`.

---

### 6. Text below 12 px — medium impact

Nine to eleven px labels carry real information: `LIVE`, `CONNECTING…`, `Platform Utama`,
and every counter badge (`0`, `12`). At 11 px on a 390 px viewport against a dark red-tinted
surface, these are legible on a good panel and mush on a cheap one. They also shrink the
perceived quality of the whole page, because the smallest text sets the floor.

**Fix.** Floor at 12 px for anything a user must read. Keep 11 px only for decorative
letterspaced eyebrows, and add `font-variant-numeric: tabular-nums` to counters so the
`0 → 12` load transition does not shift width.

---

### 7. Design-token debt — medium impact

Measured inconsistencies in the shipped CSS:

- **Ten distinct radii**: `0`, `3px`, `4px`, `14px`, `.25rem`, `.375rem`, `.5rem`, `.75rem`,
  `2xl`, `3xl`, plus `full`. No rule explains which applies where.
- **No elevation system.** The only shadows are Tailwind's default variables; depth is
  carried by `border border-white/…` alone, which is why cards read as flat outlines rather
  than surfaces.
- **Magic font sizes** outside the scale: `9px`, `10px`, `11px`, `13px`, `75%`, `80%`.
- **Semantic colour collision.** `red-500`/`red-600` (81 and 47 occurrences) serve as brand
  accent, active state, *and* destructive/error colour. When the accent and the error colour
  are the same hue, an error stops reading as an error — and a brand moment reads as a
  failure.

**Fix.** Three radii, three elevations, one semantic mapping:

```css
:root {
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-pill: 999px;

  --elev-1: 0 1px 2px rgb(0 0 0 / .4);
  --elev-2: 0 8px 24px -8px rgb(0 0 0 / .6);
  --elev-3: 0 24px 60px -20px rgb(0 0 0 / .75);

  --accent: #ff3b30;        /* brand + CTA only */
  --danger: #e5484d;        /* destructive only  */
  --warn:   #f99c00;
  --ok:     #10b981;
  --text:   #e7e7ea;
  --muted:  #9aa0ab;
  --surface:#0e1017;
  --line:   rgb(255 255 255 / .08);
}
```

`--muted` on `--surface` measures 7.4:1 and `--text` measures 15.9:1 — both safely above AA,
so the palette does not need to be re-chosen, only re-assigned.

---

### 8. Heading semantics — medium impact

Every view ships two `<h1>` elements: the brand (`Tiki-Tiki Fire Hub`) and the view title
(`Tiki Prompt Vault`, `Community Voting`, `Beta Lab Sandbox`, `AKTIVASI SUPPORTER ACCESS KEY`).
The order also breaks — `h2` appears before `h1` in the document, and `h2` is immediately
followed by `h1`.

Screen-reader users navigate by heading level; two `h1`s and a skipped level makes the
document outline unusable even though the visual hierarchy looks fine.

**Fix.** Brand becomes a `<p class="wordmark">` or an image with `alt` (it is already
letterspaced type, not text anyone needs read). Each view keeps exactly one `h1`, and the
sidebar section labels become `h2` or `aria-labelledby` targets rather than raw `<div>`s.

---

### 9. Motion has no off switch — medium impact

The page runs a boot overlay, a full-viewport `<canvas>` at `opacity: .8`, and seven CSS
animations. `prefers-reduced-motion` appears **zero** times in the stylesheet, and no
`prefers-color-scheme` handling exists either.

For users with vestibular sensitivity this is a hard stop, and on mid-range Android the
continuous canvas is a measurable battery cost on a page that is otherwise static text.

**Fix.**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
  canvas[data-decorative] { display: none; }
}
```

Then gate the boot overlay behind the same query, and honour it in JS with
`matchMedia('(prefers-reduced-motion: reduce)')` before starting the canvas loop.

---

### 10. Brand surface: three names above the fold — low impact

The landing view stacks: `T I K I - T I K I F I R E H U B` (letterspaced), then
`Community Supporter`, then `PLATFORM & PROMPT VAULT`, then an `h1` that repeats
`Tiki-Tiki Fire Hub`. Four lines, one name, one idea.

The letterspacing on the wordmark is also the only place in the product where tracking is
used that aggressively, so it reads as decoration rather than identity.

**Fix.** One wordmark, one positioning line, one `h1`. If the name must appear twice, make the
second instance the product promise instead — "Vault prompt & lisensi komunitas".

---

### 11. Content and state contradictions — low impact, high trust cost

- Sidebar reads `AI Agent (Idle Workspace)` with a `LIVE` badge on the same row.
- Counters render `0` before data loads, then jump to `12`, so the first paint claims the
  vault is empty.
- The legal page is 7,590 characters of liability text with a duplicate `h1` and a `v2.5 Legal`
  badge, and reads as a wall — four FAQ entries are the only part a user actually needs.
- Two `h3` headings begin with `🔐`, inside an otherwise icon-free editorial system.

**Fix.** Pick one state word (`Idle` / `Connected` / `Streaming`) and drive the badge from it.
Render `—` rather than `0` until the count resolves. Split the legal page: `/legal` for the
short version with a sticky table of contents, `/terms` for the full liability text. Replace
`🔐` with the existing lock icon component already used in the header.

---

## Priority

| # | Fix | Effort | Impact |
|---|---|---|---|
| 1 | Route every section, real `<nav>`, `aria-current` | M | High — shareability, back button, accessibility |
| 2 | Separate gate state from empty state | S | High — conversion and honesty |
| 3 | Fix font loading or remove the fonts | S | High — the design renders as intended |
| 4 | Single `h1` per view, correct heading order | S | Medium — document outline |
| 5 | 44 px tap targets, 12 px text floor | S | Medium — mobile usability |
| 6 | Honour `prefers-reduced-motion` | S | Medium — accessibility, battery |
| 7 | Collapse to 3 radii, 3 elevations, semantic colours | M | Medium — perceived polish |
| 8 | Replace boot overlay with instant shell | M | Medium — first impression |
| 9 | Fix state contradictions and counter placeholders | S | Low — trust |
| 10 | Restructure the legal page | M | Low — load, comprehension |

Effort: S = under a day, M = one to three days.

Items 1 through 6 are the ones a first-time visitor notices. Items 7 and 8 are the ones that
make the product feel made rather than assembled. Everything else is polish on a foundation
that is already sound.
