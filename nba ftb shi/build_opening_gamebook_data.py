"""Extract first-quarter opening evidence from the downloaded official NBA PDFs.

Only the first quarter is ingested. Source page numbers, PDF hashes and the
printed basket/foul/free-throw descriptions are retained for every and-one.
Neither a one-shot free throw alone nor a technical free throw proves an and-one.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import unicodedata
import threading
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
TARGET = 'first-team-score-including-free-throws'
PDFIUM_LOCK = threading.Lock()


def norm(value):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower())


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def aliases(name):
    words = name.replace('.', '').split()
    first, last = words[0], ''.join(words[1:])
    result = {norm(first[:i] + last) for i in range(1, len(first) + 1)}
    if words[-1].lower() in ('jr', 'ii', 'iii', 'iv'):
        result |= {norm(first[:i] + ''.join(words[1:-1])) for i in range(1, len(first) + 1)}
    return result


def quarter_pages(pdf, cache, expected_hash):
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    cached = None
    if cache.exists():
        result = read(cache)
        if result['sha256'] == expected_hash:
            cached = result['pages']
            if any('End of 1st QUARTER' in p['text'] for p in cached if not p.get('box')):
                return cached
    raw = pdf.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError('PDF hash changed: ' + str(pdf))
    # PDFium locates headers quickly; pypdf preserves the printed two-column layout.
    indexes = []
    with PDFIUM_LOCK, pdfium.PdfDocument(raw) as document:
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            textpage.close()
            page.close()
            if 'OFFICIAL PLAY-BY-PLAY' in text[:500]:
                if '1st QUARTER' in text or indexes and '2nd QUARTER' not in text:
                    indexes.append(index)
                elif indexes:
                    break
    if not indexes:
        raise ValueError('First-quarter play-by-play missing: ' + str(pdf))
    if cached and {p['page']-1 for p in cached if not p.get('box')} == set(indexes):
        return cached
    reader = PdfReader(pdf)
    pages = [{'page': index + 1, 'text': reader.pages[index].extract_text(extraction_mode='layout')} for index in indexes]
    # The first-quarter box disambiguates rare same-team abbreviated surnames.
    pages.insert(0, {'page': 2, 'box': True, 'text': reader.pages[1].extract_text(extraction_mode='layout')})
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({'sha256': expected_hash, 'pages': pages}, ensure_ascii=False), encoding='utf-8')
    return pages


def parse_pages(pages, game, record):
    alias = defaultdict(set)
    names = {}
    for row in record['player_rows']:
        if row['espn_player_id'] and row['played']:
            pid = str(row['espn_player_id'])
            names[pid] = row['nba_name']
            for key in aliases(row['nba_name']):
                alias[(row['team'], key)].add(pid)
    events = []
    score = [0, 0]
    left_team = right_team = None
    for page in pages:
        if page.get('box'):
            continue
        lines = page['text'].splitlines()
        header = next(line for line in lines if re.match(r'^Time\s+', line))
        middle = header.index('Score')
        lead_end = header.index('Lead') + 4
        right_start = lead_end + re.search(r'\S', header[lead_end:]).start()
        # The two team headers always print HOME on the left, VISITOR on the right.
        left_team, right_team = game['home'], game['away']
        for lineno, line in enumerate(lines, 1):
            m = re.match(r'^(\d{1,2}:\d{2}(?:\.\d+)?|:\d{2}(?:\.\d+)?)\s+', line)
            if not m:
                continue
            clock = m[1]
            left = line[m.end():middle].strip()
            center = line[middle:right_start]
            right = line[right_start:].strip()
            # Long shot names wrap within their own printed team column.
            for continuation in lines[lineno:]:
                if re.match(r'^(\d{1,2}:\d{2}(?:\.\d+)?|:\d{2}(?:\.\d+)?)\s+', continuation):
                    break
                if 'Copyright' in continuation or 'End of ' in continuation:
                    break
                if not continuation.strip():
                    continue
                start = len(continuation)-len(continuation.lstrip())
                if 8 <= start < middle:
                    left += ' ' + continuation[:middle].strip()
                elif start >= right_start:
                    right += ' ' + continuation[right_start:].strip()
            sm = re.search(r'(?<!\d)(\d+)-(\d+)(?!\d)', center)
            new_score = [int(sm[1]), int(sm[2])] if sm else score[:]
            deltas = [new_score[i]-score[i] for i in [0, 1]]
            if any(d < 0 or d > 3 for d in deltas) or all(deltas):
                raise ValueError(f"Invalid first-quarter score progression {game['id']} {line}")
            for side, text in [(0, left), (1, right)]:
                if not text:
                    continue
                team = [left_team, right_team][side]
                is_ft = bool(re.search(r'Free Throw', text, re.I))
                is_shot = is_ft or bool(re.search(r'\b(Shot|Layup|Dunk|Hook|Tip|Finger Roll|Alley Oop|Putback)\b', text, re.I))
                if re.search(r'JUMP BALL|REBOUND|TURNOVER|BLOCK|STEAL|Violation|^TIP TO', text, re.I):
                    is_shot = False
                # Steals/blocks on the opposite side of a shot are separate events.
                if deltas[side] and not is_shot:
                    raise ValueError(f"Unrecognized scoring description {game['id']} {text}")
                actor = re.match(r'^(?:MISS\s+)?([^\s]+)', text)
                token = actor[1] if actor else ''
                ids = alias.get((team, norm(token)), set())
                points = deltas[side]
                if points and 'MISS ' in text:
                    raise ValueError('MISS with scoring delta: ' + game['id'])
                events.append({'sequence': len(events)+1, 'period': 1, 'clock': clock,
                    'team': team, 'text': text, 'page': page['page'], 'line': lineno,
                    'athleteIds': sorted(ids), 'actorToken': token,
                    'points': points, 'scoringPlay': bool(points), 'isAttempt': is_shot,
                    'isFreeThrow': is_ft, 'homeScore': new_score[0], 'awayScore': new_score[1]})
            score = new_score
    # Use first-quarter shooting totals to resolve ambiguous abbreviated actors.
    quarter = {}
    quarter_points = Counter()
    box_team = None
    for line in pages[0]['text'].splitlines():
        if line.startswith('VISITOR:'):
            box_team = game['away']
        elif line.startswith('HOME:'):
            box_team = game['home']
        m = re.match(r'^\s*\d{1,2}\s+(.+?)\s{2,}(?:[FGC]\s+)?\d{1,2}:\d{2}\s+(.+)$', line)
        if m:
            values = m[2].split()
            if len(values) == 16:
                row_teams = {r['team'] for r in record['player_rows'] if norm(r['nba_name']) == norm(m[1])}
                row_team = next(iter(row_teams)) if len(row_teams) == 1 else box_team
                if row_team:
                    quarter[(row_team, norm(m[1]))] = list(map(int, values[:6]))
                    quarter_points[row_team] += int(values[-1])
    if quarter_points[game['home']] != score[0] or quarter_points[game['away']] != score[1]:
        raise ValueError(f"First-quarter play-by-play score differs from official quarter box {game['id']} {score} {dict(quarter_points)}")
    by_token = defaultdict(list)
    for event in events:
        if event['isAttempt']:
            by_token[(event['team'], event['actorToken'])].append(event)
    for (team, token), attempts in by_token.items():
        ids = alias.get((team, norm(token)), set())
        if len(ids) > 1:
            fg = [e for e in attempts if not e['isFreeThrow']]
            threes = [e for e in fg if '3PT' in e['text']]
            ft = [e for e in attempts if e['isFreeThrow']]
            actual = [sum(e['scoringPlay'] for e in fg), len(fg), sum(e['scoringPlay'] for e in threes), len(threes), sum(e['scoringPlay'] for e in ft), len(ft)]
            ids = {pid for pid in ids if quarter.get((team, norm(names[pid]))) == actual}
            if len(ids) == 1:
                for event in events:
                    if event['team'] == team and event['actorToken'] == token:
                        event['athleteIds'] = sorted(ids)
                        event['identityMethod'] = 'PDF abbreviation and first-quarter shooting totals'
    first_scores, first_fg, first_attempts, first_fg_attempts = {}, {}, {}, {}
    for event in events:
        team = event['team']
        if event['isAttempt']:
            first_attempts.setdefault(team, event)
            if not event['isFreeThrow']:
                first_fg_attempts.setdefault(team, event)
        if event['scoringPlay']:
            first_scores.setdefault(team, event)
            if not event['isFreeThrow']:
                first_fg.setdefault(team, event)
    for group in [first_scores, first_fg, first_attempts, first_fg_attempts]:
        if set(group) != {game['home'], game['away']}:
            raise ValueError('Incomplete opening groups: ' + game['id']+' '+str(list(group)))
        for event in group.values():
            if len(event['athleteIds']) > 1 and event['isAttempt']:
                column = (4 if event['scoringPlay'] else 5) if event['isFreeThrow'] else (2 if event['scoringPlay'] else 3) if '3PT' in event['text'] else (0 if event['scoringPlay'] else 1)
                ids = {pid for pid in event['athleteIds'] if quarter.get((event['team'],norm(names[pid])), [0]*6)[column] > 0}
                if not event['isFreeThrow'] and '3PT' not in event['text']:
                    ids = {pid for pid in ids if (quarter[(event['team'],norm(names[pid]))][column]-quarter[(event['team'],norm(names[pid]))][column+2]) > 0}
                if len(ids) == 1:
                    event['athleteIds'] = sorted(ids)
                    event['identityMethod'] = 'Unique eligible shooter in official first-quarter box'
            if len(event['athleteIds']) != 1:
                if group is first_attempts or group is first_fg_attempts:
                    event['identityUnresolved'] = True
                    continue
                raise ValueError(f"Unresolved opening identity {game['id']} {event['team']} {event['text']} {event['athleteIds']}")
    for event in events:
        if event['isFreeThrow']:
            same_clock = [e for e in events if e['clock'] == event['clock']]
            linked_actors = {e['athleteIds'][0] for e in same_clock if e['sequence'] < event['sequence'] and e['team'] == event['team'] and e['actorToken'] == event['actorToken'] and len(e['athleteIds']) == 1 and e['scoringPlay'] and not e['isFreeThrow']}
            if len(linked_actors) == 1 and linked_actors.issubset(event['athleteIds']):
                event['athleteIds'] = sorted(linked_actors)
            basket = [e for e in same_clock if e['sequence'] < event['sequence'] and e['team'] == event['team'] and e['athleteIds'] == event['athleteIds'] and e['scoringPlay'] and not e['isFreeThrow']]
            foul = [e for e in same_clock if e['sequence'] < event['sequence'] and e['team'] != event['team'] and 'S.FOUL' in e['text']]
            special = bool(re.search(r'technical|flagrant|clear path|take foul|transition', event['text'], re.I))
            one = '1 of 1' in event['text']
            event['andOne'] = bool(one and basket and foul and not special)
            event['freeThrowType'] = 'and-one' if event['andOne'] else 'special' if special else 'one-shot-unconfirmed' if one else 'two-shot' if 'of 2' in event['text'] else 'three-shot' if 'of 3' in event['text'] else 'unclassified'
            if event['andOne']:
                event['linkedBasketSequence'] = basket[-1]['sequence']
                event['linkedFoulSequence'] = foul[-1]['sequence']
    def score_event(event):
        actor = event['athleteIds'][0]
        shot = 'ft' if event['isFreeThrow'] else 'threeP' if event['points'] == 3 else 'dunk' if 'Dunk' in event['text'] else 'tip' if 'Tip' in event['text'] else 'hook' if 'Hook' in event['text'] else 'layup' if 'Layup' in event['text'] else 'mid'
        extra = [e for e in events if e.get('linkedBasketSequence') == event['sequence']]
        return {**event, 'id': actor, 'name': names[actor], 'shot': shot,
            'andOneAwarded': bool(extra), 'andOneAttempts': len(extra),
            'andOneMade': sum(e['scoringPlay'] for e in extra), 'andOneFreeThrows': extra}
    cut = max(e['sequence'] for e in first_fg.values())
    last_clock = events[cut-1]['clock']
    retained = [e for e in events if e['sequence'] <= cut or e['clock'] == last_clock]
    return {'firstScores': {t: score_event(e) for t,e in first_scores.items()},
        'firstFieldGoals': {t: score_event(e) for t,e in first_fg.items()},
        'firstAttempts': first_attempts, 'firstFieldGoalAttempts': first_fg_attempts,
        'orderedEvents': retained, 'quarterAttemptCount': sum(e['isAttempt'] for e in events)}


def one_job(job):
    library, cache_root, game, record = job
    try:
        pages = quarter_pages(library/record['pdf_path'], cache_root/(game['id']+'.json'), record['sha256'])
        result = parse_pages(pages, game, record)
        return game['id'], {**result, 'source': record['source_url'], 'sourceHash': record['sha256'], 'date': game['date'], 'phase': game['phase']}, None
    except Exception as exc:
        return game['id'], None, str(exc)


def build(base=BASE, library=None, workers=6, limit=None):
    library = Path(library or base.parent/'nba_gamebook_library/2025-26')
    evidence = read(base/'analyst_data.json')
    jobs = [(library, library/'text/opening_quarter', g, read(library/'records'/(g['id']+'.json'))) for g in evidence['games'][:limit]]
    games, errors = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for gid, result, error in pool.map(one_job, jobs):
            if error:
                errors[gid] = error
            else:
                games[gid] = result
            if (len(games)+len(errors)) % 100 == 0:
                print(json.dumps({'processed': len(games)+len(errors), 'verified': len(games), 'errors': len(errors)}), flush=True)
    report = {'gamesExpected': len(jobs), 'verified': len(games), 'errors': errors,
        'firstScoreDifferences': [], 'firstFieldGoalDifferences': [],
        'unresolvedOpeningAttempts': [{'game':gid,'target':key,'team':team,'event':event} for gid,g in games.items() for key in ['firstAttempts','firstFieldGoalAttempts'] for team,event in g[key].items() if event.get('identityUnresolved')]}
    for g in evidence['games'][:limit]:
        if g['id'] not in games:
            continue
        for key, output in [('firstScores','firstScoreDifferences'),('firstFieldGoals','firstFieldGoalDifferences')]:
            for team in [g['home'], g['away']]:
                old, new = g[key][team], games[g['id']][key][team]
                if old.get('id') != new['id'] or old.get('points') != new['points'] or old.get('clock','').lstrip('0') != new['clock'].lstrip('0'):
                    report[output].append({'game':g['id'],'team':team,'previous':old,'official':new})
    (base/'opening_extraction_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:len(v) if isinstance(v,(list,dict)) else v for k,v in report.items()}), flush=True)
    if errors or limit:
        return report
    text = json.dumps(games, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    result = {'meta': {'season': evidence['meta']['season'], 'games': len(games),
        'parentEvidenceContentHash': evidence['meta']['evidenceContentHash'],
        'contentHash': hashlib.sha256(text.encode()).hexdigest(),
        'source': 'NBA official gamebook first-quarter play-by-play',
        'andOneRule': 'Same shooter and clock: made field goal, opposing shooting foul, subsequent non-special free throw 1 of 1; misses count as awarded attempts.',
        'scope': 'Opening events through both teams first made field goals and all events at the final opening clock; all other quarters not ingested.'}, 'games': games}
    serialized = json.dumps(result, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    (base/'opening_data.json').write_text(serialized, encoding='utf-8')
    (base/'opening_data.js').write_text('window.__FTB_OPENING_DATA__ = '+serialized+';\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--cache-shard', type=int)
    parser.add_argument('--shards', type=int, default=4)
    args = parser.parse_args()
    if args.cache_shard is not None:
        library = BASE.parent/'nba_gamebook_library/2025-26'
        evidence = read(BASE/'analyst_data.json')
        done = 0
        for index, game in enumerate(evidence['games']):
            if index % args.shards != args.cache_shard:
                continue
            record = read(library/'records'/(game['id']+'.json'))
            quarter_pages(library/record['pdf_path'], library/'text/opening_quarter'/(game['id']+'.json'), record['sha256'])
            done += 1
            if done % 100 == 0:
                print(json.dumps({'shard': args.cache_shard,'cached': done}), flush=True)
        print(json.dumps({'shard': args.cache_shard,'cached': done,'complete': True}), flush=True)
        raise SystemExit(0)
    build(workers=args.workers, limit=args.limit)
