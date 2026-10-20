
#!/usr/bin/env python3
"""Conservative GotSport scraper with diagnostic logging.

Never overwrite standings when GotSport is blocked or unparseable.
"""

import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "matches.json"
STATUS = ROOT / "data" / "sync-status.json"
TEAMS = json.loads((ROOT / "data" / "teams.json").read_text())

URL = (
    "https://system.gotsport.com/org_event/events/48745/"
    "schedules?date=All&group=528635"
)


def name_id(value):
    """Resolve an exact known team name."""
    value = re.sub(r"\s+", " ", value).strip().lower()

    for key, name in TEAMS.items():
        if value == re.sub(r"\s+", " ", name).strip().lower():
            return key

    return None


def parse_html(html):
    """Extract validated completed matches from GotSport rows."""
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style"]):
        element.decompose()

    text = soup.get_text(" ", strip=True).lower()

    blocking_signals = (
        "verify you are human",
        "just a moment...",
        "captcha",
        "cloudflare ray id",
    )

    if any(signal in text for signal in blocking_signals):
        raise ValueError("GotSport bot verification detected")

    matches = []

    for tr in soup.select("tr"):
        cells = [
            re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
            for cell in tr.select("th,td")
        ]

        if len(cells) < 4:
            continue

        match = re.search(
            r"\b(7\d{3})\b",
            " ".join(cells[:2]),
        )

        score = next(
            (
                re.fullmatch(
                    r"(\d{1,2})\s*[-–]\s*(\d{1,2})",
                    cell,
                )
                for cell in cells
                if re.fullmatch(
                    r"\d{1,2}\s*[-–]\s*\d{1,2}",
                    cell,
                )
            ),
            None,
        )

        if not match or not score:
            continue

        names = [
            (index, name_id(cell))
            for index, cell in enumerate(cells)
            if name_id(cell)
        ]

        if len(names) != 2:
            continue

        date = next(
            (
                re.search(
                    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|"
                    r"Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d\d",
                    cell,
                    re.I,
                )
                for cell in cells
                if re.search(
                    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|"
                    r"Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d\d",
                    cell,
                    re.I,
                )
            ),
            None,
        )

        if not date:
            continue

        date_value = dt.datetime.strptime(
            date.group().replace(",", ""),
            "%b %d %Y",
        ).date().isoformat()

        matches.append([
            int(match.group()),
            date_value,
            names[0][1],
            names[1][1],
            int(score.group(1)),
            int(score.group(2)),
        ])

    return matches


def print_diagnostics(page, response, html):
    """Print information needed to diagnose GotSport access."""
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== GOTSPORT DIAGNOSTICS ==========")
    print("Requested URL:", URL)
    print("Final URL:", page.url)
    print(
        "HTTP status:",
        response.status if response else "unknown",
    )
    print("Page title:", page.title())
    print("HTML length:", len(html))
    print("Table rows:", len(soup.select("tr")))
    print("Table cells:", len(soup.select("td")))
    print("Forms:", len(soup.select("form")))

    text = soup.get_text(" ", strip=True)

    print("\n--- PAGE TEXT SAMPLE ---")
    print(text[:2000])

    print("\n--- MATCH NUMBER CHECK ---")
    for match_number in ("7131", "7133", "7145", "7152"):
        print(
            match_number,
            "present:",
            match_number in html,
        )

    print("\n--- TABLE ROW SAMPLES ---")
    for index, tr in enumerate(soup.select("tr")[:5]):
        print(
            f"Row {index + 1}:",
            tr.get_text(" ", strip=True)[:500],
        )

    print("========== END DIAGNOSTICS ==========\n")


def main():
    checked = dt.datetime.now(
        ZoneInfo("America/Los_Angeles")
    ).isoformat(timespec="seconds")

    status = {
        "checkedAt": checked,
        "status": "blocked",
        "message": "",
    }

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )

            page = browser.new_page(
                locale="en-US",
                timezone_id="America/Los_Angeles",
            )

            response = page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(5000)

            html = page.content()

            # Diagnostic output for GitHub Actions logs.
            print_diagnostics(page, response, html)

            browser.close()

        if response is None or response.status >= 400:
            raise ValueError(
                "HTTP "
                + str(response.status if response else "unknown")
            )

        found = parse_html(html)

        print("Validated completed matches:", len(found))

        # Never replace existing standings with incomplete data.
        if len(found) < 3:
            raise ValueError(
                f"Only {len(found)} validated matches; "
                "page may be blocked or markup changed"
            )

        original = json.loads(DATA.read_text())

        merged = {
            match[0]: match
            for match in original["matches"]
        }

        changed = 0

        for match in found:
            if merged.get(match[0]) != match:
                changed += 1

            merged[match[0]] = match

        if changed:
            original["matches"] = sorted(
                merged.values(),
                key=lambda match: (match[1], match[0]),
            )

            original["pending"] = [
                match
                for match in original.get("pending", [])
                if match[0] not in merged
            ]

            original["updatedAt"] = checked
            original["source"] = (
                "GotSport public schedule "
                "(automated, validated)"
            )

            DATA.write_text(
                json.dumps(original, indent=2) + "\n"
            )

        status.update(
            status="success",
            message=(
                f"{len(found)} matches validated; "
                f"{changed} new/updated"
            ),
        )

    except Exception as exc:
        status.update(
            status="blocked",
            message=str(exc)[:180],
        )

        print("COLLECTION ERROR:", str(exc))

    STATUS.write_text(
        json.dumps(status, indent=2) + "\n"
    )

    print("\nFINAL SYNC STATUS:")
    print(json.dumps(status, indent=2))

    # Preserve the public website even if collection fails.
    return 0


if __name__ == "__main__":
    sys.exit(main())
