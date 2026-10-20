# SOCAL GU9 Flight 1 Southwest — community standings

Unofficial public standings for [GotSport event 48745, group 528635](https://system.gotsport.com/org_event/events/48745/schedules?date=All&group=528635). Not affiliated with SOCAL or GotSport.

## Publish for free using GitHub Pages

1. Create a GitHub repository, for example `socal-gu9-standings` (public if you want public Pages on GitHub Free).
2. Upload **all files, including `.github/workflows/`** to the `main` branch (or push the unzipped directory using Git).
3. In **Settings → Pages**, choose **Source: GitHub Actions**.
4. Run the **Publish standings website** workflow once (Actions tab), or push another commit to `main`.
5. Your public URL will look like `https://YOUR-USERNAME.github.io/socal-gu9-standings/`.
6. In **Settings → Actions → General → Workflow permissions**, ensure the workflow has permission to write repository contents if scheduled collection reports a 403 when pushing (the workflow requests `contents: write`).

No domain, database, API key, or paid hosting is required.

## Scheduled updates

The `Update standings from GotSport` GitHub Actions workflow runs at **Saturday and Sunday, 5:00 PM America/Los_Angeles**, including DST transitions. The cron schedule uses both possible UTC hours, and a Pacific-time guard prevents double execution. GitHub's scheduled workflows are **best-effort and can be delayed**; they are not guaranteed to run at the exact minute. GitHub disables schedules in inactive public repositories after extended inactivity; check the Actions tab if updates stop.

The collector loads GotSport in a headless browser and only accepts matches with an exact known team, numeric result, date and match number. It merges by match number, so repeat checks do not duplicate games. It preserves previous results if GotSport shows CAPTCHA, changes its HTML, or cannot be parsed. Check `data/sync-status.json` for status. If the page format changes, update `scripts/sync.py`.

**Important:** This collector is intentionally conservative. The current GotSport page has been observed to show CAPTCHA to automated visitors. Automatic collection is **not guaranteed**; verify the first live run. The parser has not been validated against a current live GotSport HTML page in this environment. Never try to bypass CAPTCHA; use the manual import fallback instead.

## Manual fallback

On the website, click **Import results**, then either paste one or more lines in this format:

```text
7154 | 2026-10-24 | Beach Futbol Club GU09 SB W. Lopez | 2 - 1 | So Cal Blues GU09 Blue
```

or upload a `matches.json` file in the same format as `data/matches.json`. Click **Preview locally**. The standings will recalculate in that browser. Click **Download JSON** and replace `data/matches.json` in the GitHub repository (commit to `main`). GitHub Pages then republishes the updated table. **Local imports are not public until committed**; there is deliberately no unauthenticated public write endpoint.

To correct a score, import a line with the same GotSport match number: it replaces the prior result. For canceled or postponed games, remove any erroneously completed entry directly from the JSON; pending matches are not included in standings.

## Table calculation

- MP = completed matches
- W, L, D = wins, losses, draws (same column order as SOCAL U11 example)
- GF, GA, GD = goals for, against, difference
- PTS = 3 × W + D
- PPG = PTS / MP
- Rank by exact (unrounded) PPG, then GD, then GF, then alphabetical name if still tied.
- Canceled, postponed, unscored matches excluded.

## Data provenance

The initial 18 completed matches were transcribed from the results the user supplied through October 17, 2026. It is a verified **user-supplied snapshot**, not proof of successful automatic scraping. `data/sync-status.json` reports whether scheduled scraping has run.

## Local preview

```bash
python3 -m http.server 8000
# Open http://localhost:8000
```

## Quick integrity checks

```bash
node tests/standings.test.cjs
python -m py_compile scripts/sync.py
```
