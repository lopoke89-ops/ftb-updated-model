"""Read public Tennessee prices and retain minimal market envelopes for parser replay."""
import argparse
import json
from pathlib import Path
import fanduel_odds as fd

ROOT = Path(__file__).resolve().parents[1]

def minimize(payload):
    layout=payload.get('layout', {})
    return {'attachments': payload['attachments'], 'layout': {
        'tabs': {k:{'title':v.get('title')} for k,v in layout.get('tabs',{}).items()},
        'cards': {k:{'title':v.get('title'),'attachmentsFullyLoaded':v.get('attachmentsFullyLoaded')} for k,v in layout.get('cards',{}).items()}}}

class AuditedClient(fd.Client):
    def __init__(self):
        super().__init__()
        self.envelopes = []

    def fd(self, endpoint, **params):
        payload, digest = super().fd(endpoint, **params)
        if endpoint == 'event-page':
            markets = {}
            for key, value in payload.get('attachments', {}).get('markets', {}).items():
                if not fd.market_contract(value):
                    continue
                market = {k: value[k] for k in ['marketId', 'eventId', 'eventTypeId', 'inPlay', 'marketType', 'marketName', 'marketStatus'] if k in value}
                market['runners'] = [{k: r[k] for k in ['selectionId', 'runnerName', 'result', 'handicap', 'runnerStatus', 'isPlayerSelection', 'winRunnerOdds'] if k in r} for r in value.get('runners', [])]
                markets[key] = market
            self.envelopes.append({'eventId': params['eventId'], 'tab': params['tab'], 'originalResponseSha256': digest,
                                   'payload': minimize({'attachments': {'events': {k:{field:v[field] for field in ['eventId','eventTypeId','competitionId','name','openDate','inPlay'] if field in v} for k,v in payload.get('attachments', {}).get('events', {}).items() if k==str(params['eventId'])}, 'markets': markets}, 'layout': payload.get('layout', {})})})
        return payload, digest

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output
    if any((out/n).exists() for n in ['live-price-snapshot.json','live-market-evidence.json']):parser.error('Choose a new folder; earlier captures must remain unchanged')
    client = AuditedClient()
    snapshot = fd.capture(client)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'live-price-snapshot.json').write_text(json.dumps(snapshot, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    (out / 'live-market-evidence.json').write_text(json.dumps({'scope': 'Public accepted-market fields and original response hashes. Public app identifier, request query and all account operations excluded. This projection is not the original complete response.', 'capturedAt': snapshot['checkedAt'], 'envelopes': client.envelopes}, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    quotes = [q for f in snapshot['fixtures'].values() for q in f['quotes']]
    print(json.dumps({'checkedAt': snapshot['checkedAt'], 'fixtures': len(snapshot['fixtures']), 'quotes': len(quotes), 'errors': snapshot['errors'], 'sourceEnvelopes': len(client.envelopes), 'marketIssues': sum(len(f['issues']) for f in snapshot['fixtures'].values())}), flush=True)
