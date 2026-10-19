"""Reconcile canonical GP/PPG and JavaScript full-stat aggregates against the PDF database."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from audit_ev_sources import FIELDS, ROOT, SOURCE

def main():
    library=Path(sys.argv[1]);out=ROOT/'audits/2026-10-19-ev'
    db=sqlite3.connect('file:'+(library/'gamebooks.sqlite').as_posix()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    sql='SELECT g.phase,p.espn_player_id AS id,COUNT(*) AS gp,'+','.join('SUM(p.'+v+') AS '+k for k,v in FIELDS.items())+' FROM player_game_stats p JOIN games g USING(espn_game_id) WHERE p.played=1 GROUP BY g.phase,p.espn_player_id'
    totals=[dict(r) for r in db.execute(sql)];db.close()
    by={(r['phase'],r['id']):r for r in totals};canonical=json.loads((SOURCE/'merged_dataset.json').read_text(encoding='utf-8'))
    checked=0
    for p in canonical['players'].values():
        pid=p['sourcePlayerId'];assert p['gp']==sum(r['gp'] for r in totals if r['id']==pid)
        for phase,values in p['ppgByPhase'].items():
            r=by.get((phase,pid),{'gp':0,'points':0});assert values['gp']==r['gp'];assert values['ppg']==(r['points']/r['gp'] if r['gp'] else None);checked+=1
    scratch=ROOT/'.build-tests/ev-audit-phase-totals.json';scratch.parent.mkdir(exist_ok=True)
    scratch.write_text(json.dumps(totals),encoding='utf-8', newline='\n')
    node=subprocess.run(['node',str(ROOT/'scripts/audit_parlay_totals.cjs'),str(scratch)],capture_output=True,text=True,check=True)
    js=json.loads(node.stdout)
    result={'status':'passed','canonicalPlayers':len(canonical['players']),'canonicalPhaseGPAndPPGChecks':checked,**js,'authority':'All final-box rows independently re-extracted and reconciled before these totals were checked. Percentages use summed makes and attempts; zero-minute played rows count toward GP; DNPs do not.'}
    (out/'season-totals.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8', newline='\n');print(json.dumps(result))

if __name__=='__main__':main()
