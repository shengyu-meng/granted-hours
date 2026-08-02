# Timetable dialog, full-artwork entry, and faithful-history audit

Date: 2026-07-27
Baseline: `c6b5c1e021c7348351306f4e6c4c9c964c1593b3`
Scope: pre-release audit of the third timetable feedback iteration.

## Contract verified

- The daily dialog occupies the safe usable viewport instead of opening as a low bottom sheet.
- `#dayDialogPanel` is the only vertical scroll owner; assigned rows, autonomous preview, and the live-work entry are reachable through that root.
- The decorative sediment/time rail is absent.
- Full artwork opens in a new tab with `rel="noopener"`, `from=timetable`, no `embed=calendar`, and unfolded work text.
- The main BGM playlist is latest-first. Initial playback requires a user click; post-click track advance is continuous; synchronous pause intent prevents an immediate `ended` event from restarting playback.
- Preview, GIF, BGM, archive, and live URLs are constrained to the canonical dated archive. Plain and percent-encoded traversal attempts are rejected.

## Faithful public-history boundary

- Public dates: 75
- Record-based dates: 65
- Withheld dates: 10
- Assigned-work residues: 209
- Visible masks per language: 190
- Same-day autonomous task-card sources excluded from assigned work: 5

The private, non-repository source audit binds all 75 public date summaries to source-excerpt and summary SHA-256 values. Its current issue list is empty. Position/holdings/account-exposure activity is rejected both by the history builder and the public safety scanner.

## Automated verification

- `python3 scripts/test_timetable_builder.py`: 14/14 PASS
- `python3 scripts/check_public_safety.py --root .`: PASS
- `npm audit --omit=dev --audit-level=high`: 0 vulnerabilities
- `npm run build:timetable`: PASS
- repeated source/generated build hash comparison: deterministic, 0 changed outputs
- `qa_timetable_dialog_full_artwork.mjs`: 9/9 PASS
- `qa_timetable_calendar_enrichment.mjs`: 11/11 PASS
- `qa_timetable_regressions.mjs`: PASS
- `qa_github_pages.mjs` against the local release build: PASS at 1440×900, 1024×768, 768×700, 390×844, and 421×386 touch
- Cloudflare slice dialog and regression QA: PASS
- remote media inventory: 225/225 preview, GIF, and BGM URLs returned HTTP 200

## Independent review

A clean-context Codex release review first rejected the implementation for autoplay, financial privacy leakage, a pause/ended race, and lexical URL traversal checks. Those findings were fixed and re-reviewed. Final delta verdict:

```json
{"passed":true,"security_concerns":[],"logic_errors":[],"privacy_concerns":[],"suggestions":[]}
```

Deployment and public-origin checks are performed after the audited commit is pushed.
