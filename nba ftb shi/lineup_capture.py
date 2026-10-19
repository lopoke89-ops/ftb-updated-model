"""Validate local lineup capture envelopes without changing their source times."""
import re
from datetime import datetime, timezone


def validate_lineup_capture(record, now=None):
    now = now or datetime.now(timezone.utc)
    kind, url, payload = record.get('kind'), record.get('url',''), record.get('payload')
    if not isinstance(payload, dict):
        raise ValueError('Lineup payload unavailable')
    if kind == 'NBA lineups':
        if not re.fullmatch(r'https://stats\.nba\.com/js/data/leaders/00_daily_lineups_\d{8}\.json',url) or not isinstance(payload.get('games'),list):
            raise ValueError('Unsupported NBA lineup source or payload')
        maximum = 300
    elif kind == 'ESPN depth chart':
        match = re.fullmatch(r'https://site\.api\.espn\.com/apis/site/v2/sports/basketball/nba/teams/(\d+)/depthcharts',url)
        if not match or str(payload.get('team',{}).get('id'))!=match.group(1) or not isinstance(payload.get('depthchart'),list):
            raise ValueError('Unsupported depth-chart source or payload')
        maximum = 21600
    else:
        raise ValueError('Unsupported lineup capture kind')
    captured = datetime.fromisoformat(str(record.get('capturedAt','')).replace('Z','+00:00'))
    if captured.tzinfo is None or not 0 <= (now-captured).total_seconds() <= maximum:
        raise ValueError('Lineup capture timestamp is stale or in the future')
    return True
