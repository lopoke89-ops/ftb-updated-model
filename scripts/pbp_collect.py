"""Independent PBP work queue for morning collection, including completed box batches."""
import json
import gzip
import hashlib
import shutil
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen
import full_game_pbp as pbp
from audit_full_game_openings import compare as compare_openings


def update(state,games,parent_hash=None,force=False):
    state=Path(state); library=state/'library'
    pointer=state/'pbp_database.json'; database=library/'play_by_play.sqlite'
    if not database.exists() and pointer.exists():
        ref=json.loads(pointer.read_text(encoding='utf-8'))
        try:
            database.parent.mkdir(parents=True,exist_ok=True);compressed=database.with_suffix('.gz.stage')
            with urlopen(Request(ref['url'],headers={'User-Agent':'FTB gamebook collector'}),timeout=60) as response,compressed.open('wb') as target: shutil.copyfileobj(response,target)
            if file_hash(compressed)!=ref['archiveHash']: raise ValueError('PBP archive hash mismatch')
            tmp=database.with_suffix('.stage')
            with gzip.open(compressed,'rb') as source,tmp.open('wb') as target: shutil.copyfileobj(source,target)
            if file_hash(tmp)!=ref['databaseHash']: raise ValueError('PBP database hash mismatch')
            tmp.replace(database)
        except Exception as exc:
            previous=state/'play_by_play_manifest.json'
            if previous.exists():
                old=json.loads(previous.read_text(encoding='utf-8'))
                pbp.save(state/'play_by_play_previous'/(old['contentHash']+'.json'),old)
            empty=pbp.connect(':memory:');manifest,_=pbp.summary(empty,games,parent_hash);empty.close()
            manifest['lastRestoreError']=str(exc);pbp.save(previous,manifest);return manifest,True
    db=pbp.connect(database)
    previous=state/'play_by_play_manifest.json'
    old=json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else None
    for g in games:
        path=library/'records'/(g['id']+'.json')
        try:
            r=json.loads(path.read_text(encoding='utf-8'))
            if r.get('verification_status')!='verified':raise ValueError('Latest box extraction is unresolved; retain independently verified earlier source')
            rid=pbp.revision_id(g,r)
            found=db.execute('SELECT result FROM revisions WHERE id=?',(rid,)).fetchone()
            # Partial work is independently retryable; unchanged successful components stay intact.
            if found and not force and json.loads(found[0])['status']=='verified': continue
            pdf=library/r['pdf_path']
            if not pdf.exists():
                saved=db.execute('SELECT pdf FROM sources WHERE hash=?',(r['sha256'],)).fetchone()
                if saved: raw=saved[0]
                else:
                    url=r.get('archiveUrl') or r['source_url']
                    with urlopen(Request(url,headers={'User-Agent':'FTB gamebook collector'}),timeout=30) as response: raw=response.read()
                if pbp.sha(raw)!=r['sha256']: raise ValueError('Restored PDF differs from verified box hash')
                pdf.parent.mkdir(parents=True,exist_ok=True);tmp=pdf.with_suffix('.stage');tmp.write_bytes(raw);tmp.replace(pdf)
            identity_path=library/'identity_sources'/(g['id']+'.json')
            if not identity_path.exists():
                ref=r.get('pbpIdentitySource')
                retained_result=found or db.execute('SELECT r.result FROM active a JOIN revisions r ON r.id=a.revision WHERE a.game_id=?',(g['id'],)).fetchone()
                if not ref and retained_result:
                    ref=json.loads(retained_result[0]).get('identityEvidence')
                if ref:
                    retained=db.execute('SELECT data,metadata FROM identity_sources WHERE hash=?',(ref['sha256'],)).fetchone()
                    identity_raw=retained[0] if retained else None
                    if identity_raw is None and ref.get('archiveUrl'):
                        with urlopen(Request(ref['archiveUrl'],headers={'User-Agent':'FTB collector'}),timeout=30) as response: identity_raw=response.read()
                    if identity_raw is not None:
                        if pbp.sha(identity_raw)!=ref['sha256']: raise ValueError('Identity capture hash mismatch')
                        identity_path.parent.mkdir(parents=True,exist_ok=True);identity_path.write_bytes(identity_raw);pbp.save(identity_path.with_suffix('.source.json'),ref)
            cached=db.execute('SELECT pages FROM revisions WHERE source_hash=? AND pages!=? LIMIT 1',(r['sha256'],'[]')).fetchone()
            parsed=pbp.parse_job((str(library),{**g,'season':r['season'],'source':r['source_url']},r,json.loads(cached[0]) if cached else None))
            pbp.store_result(db,library,parsed)
        except Exception as exc:
            with db: db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?,?)',(g['id'],pbp.now(),'pending',str(exc)))
    manifest,discrepancies=pbp.summary(db,games,parent_hash)
    for g in games:
        r=manifest['games'][g['id']]
        expected=g.get('sourceHash') or next((p.get('statsSourceHash') for b in g.get('teams',{}).values() for p in b.get('players',[]) if p.get('played')),None)
        if expected and r.get('sourceHash') and r['sourceHash']!=expected:
            manifest['games'][g['id']]={'date':g['date'],'status':'pending','components':{},'previousRevision':r['revision'],'previousSourceHash':r['sourceHash'],'reason':'Verified box source is newer than active event extraction; prior events withheld'}
    for g in games:
        r=manifest['games'][g['id']]
        record_path=library/'records'/(g['id']+'.json')
        if r.get('revision') and record_path.exists():
            source_record=json.loads(record_path.read_text(encoding='utf-8'))
            if source_record.get('verification_status')=='verified' and r['revision']!=pbp.revision_id(g,source_record):
                manifest['games'][g['id']]={'date':g['date'],'status':'pending','components':{},'previousRevision':r['revision'],'previousSourceHash':r.get('sourceHash'),'reason':'Parser or identity evidence revision changed; previous event interpretation withheld pending extraction'}
    for g in games:
        r=manifest['games'][g['id']]
        if not r.get('revision'): continue
        record_path=library/'records'/(g['id']+'.json')
        record=json.loads(record_path.read_text(encoding='utf-8')) if record_path.exists() else {}
        expected_opening=record.get('opening')
        if not expected_opening and record.get('verification_status')!='verified':
            retained=db.execute('SELECT metadata FROM sources WHERE hash=?',(r.get('sourceHash'),)).fetchone()
            if retained:expected_opening=json.loads(retained[0]).get('opening')
        events=[json.loads(row[0]) for row in db.execute('SELECT event FROM events WHERE revision=? ORDER BY sequence',(r['revision'],))]
        try:
            _,opening_differences=compare_openings(events,expected_opening,(g['home'],g['away'])) if expected_opening else (0,[{'reason':'independent opening extract unavailable'}])
        except Exception as exc: opening_differences=[{'reason':str(exc)}]
        r['openingVerification']={'verified':not opening_differences,'differences':opening_differences}
        if opening_differences:
            if r['status']=='verified': r['status']='partial'
            for context in r.get('eventContext',{}).values(): context['opening']={}
    manifest['statusCounts']=dict(Counter(g['status'] for g in manifest['games'].values()))
    manifest['componentVerifiedGames']={k:sum(bool(g['components'].get(k)) for g in manifest['games'].values()) for k in pbp.STATS}
    manifest.pop('contentHash',None);manifest['contentHash']=pbp.sha(pbp.packed(manifest).encode())
    manifest['attempts']={gid:{'checkedAt':checked,'status':status,'error':error} for gid,checked,status,error in db.execute('SELECT * FROM attempts')}
    # Retry timestamps are health data, not a change to statistical content identity.
    pbp.save(previous,manifest);pbp.save(state/'play_by_play_discrepancies.json',discrepancies)
    db.close();return manifest,not old or old.get('contentHash')!=manifest['contentHash']


def file_hash(path):
    with Path(path).open('rb') as file: return hashlib.file_digest(file,'sha256').hexdigest()


def archive(state,store,season,day):
    state=Path(state);database=state/'library/play_by_play.sqlite'
    if not database.exists(): return None
    database_hash=file_hash(database);pointer=state/'pbp_database.json'
    prior=json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else {}
    if prior.get('databaseHash')==database_hash:return prior
    target=state/'_runtime/play_by_play.sqlite.gz';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('wb') as file:
        with gzip.GzipFile(filename='',mode='wb',fileobj=file,mtime=0) as compressed,database.open('rb') as source:shutil.copyfileobj(source,compressed)
    url=store.content_file(target,state/'_runtime/uploads',season,day)
    ref={'url':url,'archiveHash':file_hash(target),'databaseHash':database_hash,'bytes':database.stat().st_size,'compressedBytes':target.stat().st_size}
    pbp.save(pointer,ref);return ref
