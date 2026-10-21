"""Offline release checks; never collect, publish or alter source evidence."""
import hashlib
import json
import pathlib
import subprocess
import sys
import time

OUT = pathlib.Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = ROOT / 'nba ftb shi'
START = '625a9e9dd56274bdcf1b8cb1ad01329690d257d2'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def original(relative):
    return subprocess.check_output(['git', 'show', START+':'+relative], cwd=ROOT)

def run(name, args):
    started = time.monotonic()
    result = subprocess.run(args, cwd=ROOT, capture_output=True)
    (OUT / 'test-logs').mkdir(exist_ok=True)
    (OUT / 'test-logs' / (name+'.txt')).write_bytes(result.stdout+result.stderr)
    row = {'name':name, 'exitCode':result.returncode, 'seconds':round(time.monotonic()-started, 2)}
    print(json.dumps(row), flush=True)
    return row

preserved = []
for baseline in sorted((OUT/'baseline-v1.1').iterdir()):
    relative = ('scripts/' if baseline.name=='train_first_team_ev.cjs' else 'nba ftb shi/' if baseline.name.startswith('ev_') else '')+baseline.name
    old = original(relative)
    preserved.append({'file':relative, 'startingSha256':sha(old), 'preservedSha256':sha(baseline.read_bytes()), 'same':old==baseline.read_bytes()})

# Full data, original selection files and other frozen models must not be part of this repair.
unchanged = []
for relative in ['nba ftb shi/'+name for name in (
    'analyst_data.json','analyst_data.js','parlay_data.json','parlay_data.js','merged_dataset.json',
    'ev_probability.js','ev_model.json','ev_model.js','ev_additional.js','ev_additional_model.json','ev_additional_model.js'
)]+['EV_PROTOCOL.json','EV_FORWARD_PROTOCOL.json','EV_RULES_PROFILE.json','ASSISTS_REBOUNDS_PROTOCOL.json']:
    if not (ROOT/relative).exists():
        continue
    current = (ROOT/relative).read_bytes()
    unchanged.append({'file':relative,'sha256':sha(current),'sameAsStart':current==original(relative)})

checks = [run(p.stem, ['node', str(p)]) for p in sorted((SOURCE/'tests').glob('test_*.cjs'))]
checks.append(run('independent-first-team', [sys.executable,'-B',str(OUT/'reference_first_team.py')]))
checks.append(run('python-collector-publication', [sys.executable,'-B','-m','unittest','discover','-s','scripts','-p','test_*.py']))
checks.append(run('python-opening', [sys.executable,'-B','-m','unittest','discover','-s','nba ftb shi/tests','-p','test_opening_gamebooks.py']))
target = OUT / 'candidate-model'
checks.append(run('repeat-fit', ['node','scripts/train_first_team_ev.cjs','--output-dir',str(target)]))
fit_matches = all((SOURCE/name).read_bytes()==(target/name).read_bytes() for name in ['ev_first_team_model.json','ev_first_team_model.js'])
build_target = ROOT/'.build-tests'/('ftb-repair-'+str(time.time_ns()))
checks.append(run('publication-build', [sys.executable,'-B','scripts/build_pages.py','--output',str(build_target)]))
report = {'startingRevision':START,'preservedBaseline':preserved,'unchangedEvidenceAndCountModels':unchanged,
          'repeatFitByteIdentical':fit_matches,'checks':checks,'buildOutput':str(build_target),
          'passed':all(x['same'] for x in preserved) and all(x['sameAsStart'] for x in unchanged) and fit_matches and all(x['exitCode']==0 for x in checks)}
(OUT/'VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
raise SystemExit(0 if report['passed'] else 1)
