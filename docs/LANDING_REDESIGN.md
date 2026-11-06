# Landing page — white editorial direction

Reference: the supplied Crymbo screenshot. Use its spacious white canvas, compact
black wordmark/navigation, close-set grotesk headline and monochrome footer strip.
Keep Touchstone's own identity and copy; do not reproduce the reference logo,
customer marks or claims.

The first viewport is an asymmetric two-column composition: the proposition on
the left, the existing isometric locker at middle-right. The locker opens once
on arrival and remains directly operable by its wheel or labelled control. It is
an illustration, not an account action. Reduced motion shows the open static state.
On mobile, text precedes the complete locker without horizontal scrolling.

Tokens: white #ffffff, ink #111210, muted #64665f, rule #e6e7e2, soft paper #f6f6f2,
restrained assay accent #a5812d. Existing locally bundled Geist and Geist Mono;
no new typeface, library, asset download or network dependency. 8px spacing base,
maximum content width 1312px, 24–64px outer margins. Visible keyboard focus and
44px controls. Motion only introduces the existing door mechanism (1.6s) and
150–250ms control feedback; no permanent decorative loops.

The integration strip names actual components with sandbox/testnet/local labels.
Evidence copy discloses that payments precede verification, models can be refused,
and accounts remain separate. Navigation, proof links and CTAs lead to actual
sections or the existing dashboard. Financial/security code is outside this edit.

## Review

The build and TypeScript check pass. Chromium review at 1440×900 and 390×844
confirmed middle-right placement, the full open/close mechanism, keyboard-wheel
operation, mobile navigation, no horizontal overflow, a static open state for
reduced motion and zero external requests or page errors. The old lamp and
borrowing-card scenes are no longer mounted on the landing page; their source
files are preserved. No dependency was added or changed. The favicon is a small
SVG of the actual mark instead of loading the old 138KB bitmap. Existing `/site/` static
serving is included with the frontend; root dashboard session/mutation checks are
retained.

[Browser review](../bench/results/landing-redesign/review.json).

The existing Python suite (247 tests) and pinned Metal Node suite (47 tests) also
passed after the redesign. Their controlled financial adapters send no money.
