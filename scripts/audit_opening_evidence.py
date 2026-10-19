"""Replay all hash-linked Q1 extractions and freshly re-extract a deterministic PDF sample."""
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'nba ftb shi'
sys.path.insert(0,str(SOURCE))
import build_opening_gamebook_data as opening

def main():
    library=Path(sys.argv[1])
    out=ROOT/'audits/2026-10-19-ev';out.mkdir(parents=True,exist_ok=True)
    data=json.loads((SOURCE/'analyst_data.json').read_text(encoding='utf-8', newline='\n'))
    ledger=json.loads((SOURCE/'opening_data.json').read_text(encoding='utf-8', newline='\n'))
    # Fixed positions across the whole archive, without outcome-based selection.
    sample={data['games'][i]['id'] for i in [0,50,150,300,450,600,750,900,1050,1200,1250,1321]}
    differences=[];fresh=[];replayed=0
    def one(g):
        record=json.loads((library/'records'/(g['id']+'.json')).read_text(encoding='utf-8', newline='\n'))
        cached=json.loads((library/'text/opening_quarter'/(g['id']+'.json')).read_text(encoding='utf-8', newline='\n'))
        if cached['sha256']!=record['sha256']:raise ValueError('Opening cache hash mismatch')
        parsed=opening.parse_pages(cached['pages'],g,record)
        expected={k:v for k,v in ledger['games'][g['id']].items() if k not in ['source','sourceHash','date','phase']}
        errors=[]
        if parsed!=expected:errors.append('Cached opening replay differs')
        proof=None
        if g['id'] in sample:
            pages=opening.quarter_pages(library/record['pdf_path'],ROOT/'.build-tests/ev-audit-opening'/(g['id']+'.json'),record['sha256'])
            direct=opening.parse_pages(pages,g,record)
            if direct!=expected:errors.append('Fresh PDF opening extraction differs')
            proof={'gameId':g['id'],'source':record['source_url'],'sha256':record['sha256'],'pages':[p['page'] for p in pages]}
        return g['id'],errors,proof
    with ThreadPoolExecutor(max_workers=4) as pool:
        for gid,errors,proof in pool.map(one,data['games']):
            replayed+=1
            if errors:differences.append({'gameId':gid,'errors':errors})
            if proof:fresh.append(proof)
    result={'status':'passed' if not differences else 'failed','cachedGamesReplayed':replayed,'freshPDFGames':len(fresh),'firstScoreAndFirstFGReferences':replayed*4,'freshSources':fresh,'differences':differences,
            'scope':'All hash-linked cached Q1 extractions replayed; deterministic 12-game sample freshly extracted from original PDFs. Complete original PDF hashes were independently checked in the final-box reconciliation. Full-game defensive matchups, possessions, and on/off effects are not structured.'}
    (out/'opening-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='freshSources'}))
    return bool(differences)

if __name__=='__main__':raise SystemExit(main())
