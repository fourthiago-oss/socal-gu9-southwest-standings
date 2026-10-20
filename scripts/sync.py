#!/usr/bin/env python3
"""Conservative GotSport scraper. Never overwrite results on blocked/unparseable pages."""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'matches.json'
STATUS = ROOT / 'data' / 'sync-status.json'
TEAMS = json.loads((ROOT / 'data' / 'teams.json').read_text())
URL = 'https://system.gotsport.com/org_event/events/48745/schedules?date=All&group=528635'


def name_id(s):
    s = re.sub(r'\s+', ' ', s).strip().lower()
    for k, v in TEAMS.items():
        if s == v.lower():
            return k
    return None


def parse_html(html):
    """Parse GotSport schedule table rows, validating team names and score columns."""
    soup = BeautifulSoup(html, 'html.parser')
    for bad in soup(['script', 'style']): bad.decompose()
    text = soup.get_text(' ', strip=True).lower()
    if any(x in text for x in ('verify you are human', 'just a moment...', 'captcha', 'cloudflare ray id')):
        raise ValueError('GotSport bot verification detected')
    rows = []
    for tr in soup.select('tr'):
        cells = [re.sub(r'\s+', ' ', x.get_text(' ', strip=True)).strip() for x in tr.select('th,td')]
        if len(cells) < 4: continue
        match = re.search(r'\b(7\d{3})\b', ' '.join(cells[:2]))
        score = next((re.fullmatch(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', c) for c in cells if re.fullmatch(r'\d{1,2}\s*[-–]\s*\d{1,2}', c)), None)
        if not match or not score: continue
        names = [(i, name_id(c)) for i, c in enumerate(cells) if name_id(c)]
        if len(names) != 2: continue
        date = next((re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d\d', c, re.I) for c in cells if re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d\d', c, re.I)), None)
        if not date: continue
        d = dt.datetime.strptime(date.group().replace(',', ''), '%b %d %Y').date().isoformat()
        rows.append([int(match.group()), d, names[0][1], names[1][1], int(score[1]), int(score[2])])
    return rows


def main():
    checked = dt.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
    status = {'checkedAt': checked, 'status': 'blocked', 'message': ''}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(locale='en-US', timezone_id='America/Los_Angeles')
            response = page.goto(URL, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            browser.close()
        if response is None or response.status >= 400: raise ValueError('HTTP '+str(response.status if response else 'unknown'))
        found = parse_html(html)
        # Safety guard: a page containing no identifiable scored matches must never clear the dataset.
        if len(found) < 3: raise ValueError(f'Only {len(found)} validated matches; page may be blocked or markup changed')
        original = json.loads(DATA.read_text())
        merged = {m[0]:m for m in original['matches']}
        changed = 0
        for m in found:
            if merged.get(m[0]) != m: changed += 1
            merged[m[0]] = m
        if changed:
            original['matches'] = sorted(merged.values(), key=lambda m:(m[1],m[0]))
            original['pending'] = [m for m in original.get('pending',[]) if m[0] not in merged]
            original['updatedAt'] = checked
            original['source'] = 'GotSport public schedule (automated, validated)'
            DATA.write_text(json.dumps(original,indent=2)+'\n')
        status.update(status='success',message=f'{len(found)} matches validated; {changed} new/updated')
    except Exception as exc:
        status.update(status='blocked',message=str(exc)[:180])
    STATUS.write_text(json.dumps(status,indent=2)+'\n')
    print(status)
    # No hard failure: preserve site and publish the stale-data warning.
    return 0

if __name__ == '__main__': sys.exit(main())
