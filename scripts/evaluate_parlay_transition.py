"""Evaluate frozen Parlay receipts; no probability or profitability claims."""
import argparse
import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from parlay_journal import ROOT, SOURCE, read, sealed_lines, release_hashes, hashlib

def interval(groups, reps=2000, seed=20261010):
    if len(groups) < 2:
        return None
    rng = random.Random(seed)
    blocks = list(groups.values())
    values = []
    for _ in range(reps):
        sample = [x for block in rng.choices(blocks, k=len(blocks)) for x in block]
        values.append(sum(sample)/len(sample))
    values.sort()
    return [values[int(.025*reps)], values[min(reps-1, int(.975*reps))]]

def enrich_diagnostic(report):
    """Add paired uncertainty and sample bands without rerunning model inference."""
    for key, summary in report['summary'].items():
        market, definition = key.split('|')
        rows = [r for r in report['rows'] if r['market']==market and (market!='first-team-basket' or r['target']==definition)]
        fixture, weekly = defaultdict(list), defaultdict(list)
        bands = {}
        player_differences = target_differences = 0
        for r in rows:
            n = r['teamGames']
            band = '0' if n==0 else '1-4' if n<5 else '5-9' if n<10 else '10-19' if n<20 else '20+'
            b = bands.setdefault(band, {'opportunities':0, 'models':{}, 'paired':0, 'pairedDifference':0})
            b['opportunities'] += 1
            for model in ('production','adaptive','volume','mean','no-position','no-correlation'):
                p = r.get(model)
                m = b['models'].setdefault(model, {'issued':0,'hits':0,'dnp':0})
                if p:
                    m['issued'] += 1;m['hits'] += bool(p['hit']);m['dnp'] += not p['played']
            a,p = r.get('adaptive'),r.get('production')
            if a and p:
                delta = int(a['hit'])-int(p['hit'])
                fixture[r['fixtureId']].append(delta)
                weekly[str(date.fromisoformat(r['date']).isocalendar()[:2])].append(delta)
                b['paired'] += 1;b['pairedDifference'] += delta
                player_differences += a['id'] != p['id'];target_differences += a['threshold'] != p['threshold']
        for b in bands.values():
            b['pairedDifference'] = b['pairedDifference']/b['paired'] if b['paired'] else None
            for m in b['models'].values():
                m['rate'] = m['hits']/m['issued'] if m['issued'] else None
        summary.update(fixture95Interval=interval(fixture),weekly95Interval=interval(weekly),fixtureBlocks=len(fixture),
                       earlySeasonBands=bands,playerDifferences=player_differences,thresholdDifferences=target_differences)
    report['uncertaintyMethod'] = 'Paired fixture-block bootstrap; weekly-block sensitivity; 2000 replicates; seed 20261010'
    report['phase'] = 'regular-season'
    report['promotable'] = False
    return report

def evaluate(store, protocol=None, expected_hashes=None):
    protocol = protocol or read(ROOT/'PARLAY_RESEARCH_PROTOCOL.json')
    expected_hashes = expected_hashes or release_hashes()
    protocol_hash = hashlib.sha256((ROOT/'PARLAY_RESEARCH_PROTOCOL.json').read_bytes()).hexdigest()
    configuration_hash = read(SOURCE/'parlay_research_config.json')['configurationHash']
    receipts = {r['id']:r for r in sealed_lines(Path(store)/'receipts.jsonl')}
    excluded_versions = set()
    latest = {}
    for o in sealed_lines(Path(store)/'outcomes.jsonl'):
        latest[(o['receiptId'],o['fixtureId'])] = o
    first = {}
    for o in sorted(latest.values(), key=lambda o:receipts[o['receiptId']]['receivedAt']):
        receipt = receipts[o['receiptId']]
        if receipt['recordType'] != 'prospective-research':
            continue
        export = receipt['export']
        if export.get('modelHashes') != expected_hashes or export.get('protocolHash') != protocol_hash or any((slot.get('research') or {}).get('configurationHash') != configuration_hash for slot in export['selections']):
            excluded_versions.add(receipt['id'])
            continue
        target = export['firstBasketTarget']
        for r in o['results']:
            key = (o['fixtureId'],r['team'],r['market'],r['model'],target if r['market']=='first-team-basket' else 'season-average')
            first.setdefault(key, {**r,'fixtureId':o['fixtureId'],'date':o['date'],'target':target})
    output = {}
    comparisons = protocol['comparisons']
    for market in ('first-team-basket','points','threes'):
        definitions = sorted({r['target'] for r in first.values() if r['market']==market}) if market=='first-team-basket' else ['season-average']
        for definition in definitions:
            rows = [r for r in first.values() if r['market']==market and (market!='first-team-basket' or r['target']==definition)]
            if not rows:
                continue
            key = market+'|'+definition
            by_model = {}
            lookup = {(r['fixtureId'],r['team'],r['model']):r for r in rows}
            opportunities = len({(r['fixtureId'],r['team']) for r in rows})
            for model in comparisons:
                all_rows = [r for r in rows if r['model']==model]
                issued = [r for r in all_rows if r['id'] is not None and r['provisional'] is False]
                participating = [r for r in issued if r['played']]
                by_model[model] = {'opportunities':opportunities,'issued':len(issued),'withheldOrProvisional':opportunities-len(issued),'provisional':sum(r['id'] is not None and bool(r['provisional']) for r in all_rows),
                    'hits':sum(bool(r['hit']) for r in issued),'rate':sum(bool(r['hit']) for r in issued)/len(issued) if issued else None,
                    'dnp':sum(not r['played'] for r in issued),'participatingRate':sum(bool(r['hit']) for r in participating)/len(participating) if participating else None}
            pairs = []
            fixture_blocks, week_blocks, early_blocks = defaultdict(list),defaultdict(list),defaultdict(list)
            target_differences = player_differences = 0
            for fid,team in {(r['fixtureId'],r['team']) for r in rows}:
                a,b = lookup.get((fid,team,'adaptive')),lookup.get((fid,team,'production'))
                if not a or not b or a['id'] is None or b['id'] is None or a['provisional'] is not False or b['provisional'] is not False:
                    continue
                delta = int(a['hit'])-int(b['hit']);pairs.append(delta);fixture_blocks[fid].append(delta)
                week_blocks[str(date.fromisoformat(a['date']).isocalendar()[:2])].append(delta)
                if isinstance(a.get('teamGames'),int) and a['teamGames'] <= protocol['promotion']['earlySeasonTeamGamesMax']:
                    early_blocks[fid].append(delta)
                player_differences += a['id'] != b['id'];target_differences += a['threshold'] != b['threshold']
            ci = interval(fixture_blocks);early_ci = interval(early_blocks)
            difference = sum(pairs)/len(pairs) if pairs else None
            p = protocol['promotion'];coverage = by_model['adaptive']['issued']/by_model['production']['issued'] if by_model['production']['issued'] else None
            checks = {'genuineSeasonTransition':all((s.get('fixture') or {}).get('season') == protocol['prospectiveSeason'] for receipt in receipts.values() if receipt['recordType']=='prospective-research' and receipt['id'] not in excluded_versions for s in receipt['export']['selections']) and bool(rows), 'pairedSample':len(pairs)>=p['minimumPairedSelections'],'fixtures':len(fixture_blocks)>=p['minimumDistinctFixtures'],
                'earlySample':sum(map(len,early_blocks.values()))>=p['minimumEarlySeasonPairedSelections'],
                'improvement':difference is not None and difference>=p['minimumPairedHitRateImprovement'],
                'lowerBound':ci is not None and ci[0]>p['pairedDifferenceLower95BoundAbove'],
                'coverage':coverage is not None and coverage>=p['minimumCoverageRelativeToProduction'],
                'earlyLowerBound':early_ci is not None and early_ci[0]>=p['earlySeasonDifferenceLower95BoundAtLeast']}
            output[key] = {'models':by_model,'paired':len(pairs),'fixtureBlocks':len(fixture_blocks),'difference':difference,'fixture95Interval':ci,'weekly95Interval':interval(week_blocks),
                'early95Interval':early_ci,'playerDifferences':player_differences,'thresholdDifferences':target_differences,'promotionChecks':checks,'promotable':all(checks.values())}
    return {'protocol':protocol['version'],'status':'prospective evidence evaluated' if first else 'awaiting qualifying prospective receipts and NBA PDF outcomes',
        'markets':output,'evaluatedModelHashes':expected_hashes,'configurationHash':configuration_hash,'differentReleaseReceiptsExcluded':len(excluded_versions),'researchSnapshotsExcluded':sum(r['recordType']!='prospective-research' for r in receipts.values()),'defaultModelChanged':False,
        'limitations':['Conditional historical reconstructions are not prospective evidence.','Market outcomes within fixtures are related.','This report never automatically enables a model.']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',type=Path,default=ROOT/'.parlay-research')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--diagnostic',type=Path,help='Enrich a conditional historical diagnostic instead of evaluating prospective receipts')
    args = parser.parse_args();report = enrich_diagnostic(read(args.diagnostic)) if args.diagnostic else evaluate(args.store)
    text = json.dumps(report,indent=2,allow_nan=False)+'\n'
    if args.diagnostic:
        header = json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2,allow_nan=False)
        text = header[:-2]+',\n  \"rows\": [\n'+',\n'.join('    '+json.dumps(r,separators=(',',':'),allow_nan=False) for r in report['rows'])+'\n  ]\n}\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text,encoding='utf-8',newline='\n')
    else:
        print(text)

if __name__=='__main__':
    main()
