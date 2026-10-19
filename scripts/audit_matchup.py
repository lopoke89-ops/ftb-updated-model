"""Independently reconcile Matchup outputs to the saved official NBA PDF extracts.

JavaScript exports the actual chart inputs; Python rebuilds sums and denominators
from official_boxscores/opening_data without using the Matchup implementation.
"""
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nba ftb shi'
OUT = ROOT / 'audits/2026-10-19-matchup-tab'
FIELDS = ['points', 'blocks', 'rebounds', 'offensiveRebounds', 'defensiveRebounds', 'assists']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / '.build-tests/matchup-chart-inputs.json'
    scratch.parent.mkdir(exist_ok=True)
    js = r"""
const fs=require('fs'),path=require('path'),root=process.argv[1],out=process.argv[2];
const base=path.join(root,'nba ftb shi'),M=require(path.join(base,'matchup.js')),archive=require(path.join(base,'analyst_data.json'));
const fixtures=[['BOS','DET'],['PHI','NYK'],['OKC','SAS']].map(([away,home],i)=>({id:['401909088','401909089','401909090'][i],date:'2026-10-20',away,home,season:'2026-27'}));
const current={meta:{season:'2026-27',asOfDate:null},games:[]},cases=[];
function capture(options,data=current,fixturesIn=fixtures){
 const result=M.build(data,archive,fixturesIn,{date:'2026-10-20',mode:'upcoming',trusted:true,...options});
 cases.push({options:result.options,comparisons:result.comparisons.map(c=>({...c,reference:c.reference,directions:c.directions.map(d=>({production:d.production,allowance:d.allowance}))}))});
}
for(const phase of ['all','regular-season','playoffs','regular-and-playoffs','play-in','nba-cup-final'])
 for(const window of ['0','5','10','20'])for(const headToHead of [false,true])for(const positions of ['broad','strict'])capture({phase,window,headToHead,positions});
for(const positions of ['broad','strict'])capture({positions,firstTarget:'field-goals'});
for(const date of ['2025-10-21','2025-10-23','2026-01-20','2026-06-13'])capture({date,mode:'pregame',window:'5'},archive,fixtures.map(f=>({...f,date})));
fs.writeFileSync(out,JSON.stringify(cases));
"""
    subprocess.run(['node', '-e', js, str(ROOT), str(scratch)], check=True, cwd=ROOT)
    cases = read(scratch)
    historical = read(SOURCE / 'analyst_data.json')
    boxes = read(SOURCE / 'official_boxscores.json')
    openings = read(SOURCE / 'opening_data.json')
    indexed = {g['id']: g for g in historical['games']}
    checks = Counter()
    role_sources = Counter()
    failures = []

    def eq(a, b, context):
        checks['comparisons'] += 1
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            ok = math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)
        else:
            ok = a == b
        if not ok:
            failures.append({'context': context, 'displayed': a, 'official': b})

    for gid, g in indexed.items():
        official = boxes['games'][gid]
        for key in ['date', 'home', 'away', 'phase']:
            eq(g[key], official[key], f'{gid}/{key}')
        for team, box in g['teams'].items():
            played = {p['id']: p for p in box['players'] if p['played']}
            eq(set(played), set(official['teams'][team]), f'{gid}/{team}/participation')
            for pid, p in played.items():
                record = official['teams'][team][pid]
                for k in FIELDS + ['minutesSeconds', 'officialPosition']:
                    eq(p.get(k), record.get(k), f'{gid}/{team}/{pid}/{k}')
                eq(p['statsSourceHash'], official['sha256'], f'{gid}/{team}/{pid}/PDF hash')
                role_sources['gamebook position' if record.get('officialPosition') else 'dated box-score fallback' if p.get('rawPosition') else 'unknown'] += 1
                checks['playedAppearances'] += 1
            for target in ['firstScores', 'firstFieldGoals']:
                eq(g[target][team]['id'], openings['games'][gid][target][team]['id'], f'{gid}/{team}/{target}')

    def games_for(team, opponent, o, mode):
        phase = o['phase']
        result = []
        for gid, g in boxes['games'].items():
            if team not in (g['home'], g['away']):
                continue
            if mode == 'review':
                if g['date'] > historical['meta']['asOfDate']:
                    continue
            elif g['date'] >= o['date']:
                continue
            if phase != 'all' and not (g['phase'] in ['regular-season', 'playoffs'] if phase == 'regular-and-playoffs' else g['phase'] == phase):
                continue
            if o.get('headToHead') and {g['home'], g['away']} != {team, opponent}:
                continue
            result.append((gid, g))
        result.sort(key=lambda item: (item[1]['date'], item[0]))
        return result[-int(o['window']):] if int(o['window']) else result

    def expected(team, own, games, o):
        sums = {k: {} for k in FIELDS + ['firstTeam']}
        for gid, g in games:
            actor_team = team if own else g['away'] if g['home'] == team else g['home']
            appearance = {p['id']: p for p in indexed[gid]['teams'][actor_team]['players']}
            first = openings['games'][gid]['firstFieldGoals' if o['firstTarget'] == 'field-goals' else 'firstScores'][actor_team]['id']
            seen = set()
            for pid, p in g['teams'][actor_team].items():
                raw = p.get('officialPosition') or appearance[pid]['rawPosition']
                if o['positions'] == 'strict':
                    position = raw if raw in ['PG', 'SG', 'SF', 'PF', 'C'] else 'unknown'
                else:
                    position = 'G' if raw in ['PG', 'SG', 'G'] else 'F' if raw in ['SF', 'PF', 'F'] else 'C' if raw == 'C' else 'unknown'
                for k in sums:
                    b = sums[k].setdefault(position, dict(total=0, seconds=0, appearances=0, games=0))
                    b['total'] += int(pid == first) if k == 'firstTeam' else p[k]
                    b['seconds'] += p['minutesSeconds']
                    b['appearances'] += 1
                    if position not in seen:
                        b['games'] += 1
                seen.add(position)
        return sums

    samples = []
    for ci, case in enumerate(cases):
        o = case['options']
        for c in case['comparisons']:
            for direction in c['directions']:
                for side in ['production', 'allowance']:
                    sample = direction[side]
                    team = sample['team']
                    opponent = c['fixture']['home'] if team == c['fixture']['away'] else c['fixture']['away']
                    gs = games_for(team, opponent, o, c['scopeMode'])
                    eq(sample['gameIds'], [gid for gid, _ in gs], f'{ci}/{team}/selected game IDs')
                    eq(sample['through'], gs[-1][1]['date'] if gs else None, f'{ci}/{team}/through')
                    values = expected(team, side == 'production', gs, o)
                    series = sample['own' if side == 'production' else 'against']
                    for metric, buckets in values.items():
                        eq(series[metric]['games'], len(gs), f'{ci}/{team}/{metric}/denominator')
                        eq(set(series[metric]['buckets']), set(buckets), f'{ci}/{team}/{metric}/role buckets')
                        for pos, b in buckets.items():
                            actual = series[metric]['buckets'][pos]
                            for key in b:
                                eq(actual[key], b[key], f'{ci}/{team}/{side}/{metric}/{pos}/{key}')
                    if ci == 0:
                        metric = 'points'
                        samples.append({'fixture': c['fixture']['id'], 'direction': direction['production']['team'] + ' production vs opponents against ' + direction['allowance']['team'], 'series': side, 'team': team, 'games': len(gs), 'through': sample['through'], 'positionPoints': {pos: {'points': b['total'], 'minutes': b['seconds']/60, 'per48': b['total']*2880/b['seconds'] if b['seconds'] else None, 'perGame': b['total']/len(gs) if gs else None} for pos, b in values[metric].items()}})
                    checks['scopedSeries'] += 1

    # Reconcile the full-season, all-opponents league reference independently.
    league = cases[0]['comparisons'][0]['reference']
    o = cases[0]['options']
    totals = {k: Counter() for k in FIELDS + ['firstTeam']}
    seconds = Counter()
    for team in sorted({t for g in boxes['games'].values() for t in [g['home'], g['away']]}):
        values = expected(team, True, games_for(team, None, o, 'review'), o)
        for k, buckets in values.items():
            for pos, b in buckets.items():
                totals[k][pos] += b['total']
                if k == 'points':
                    seconds[pos] += b['seconds']
    for k, positions in totals.items():
        for pos, total in positions.items():
            eq(league[k]['buckets'][pos]['total'], total, f'league/{k}/{pos}/total')
            eq(league[k]['buckets'][pos]['seconds'], seconds[pos], f'league/{k}/{pos}/seconds')

    result = {'status': 'PASS' if not failures else 'FAIL', 'games': len(indexed), 'scopeCases': len(cases), 'checks': dict(checks), 'roleSources': dict(role_sources), 'differences': failures[:30], 'differenceCount': len(failures), 'authorityBoxHash': boxes['meta']['contentHash'], 'authorityOpeningHash': openings['meta'].get('contentHash'), 'evidenceHash': historical['meta']['evidenceContentHash'], 'samples': samples}
    (OUT / 'source-reconciliation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['samples', 'differences']}, indent=2))
    if failures:
        raise SystemExit('Matchup reconciliation failed; inspect source-reconciliation.json')


if __name__ == '__main__':
    run()
