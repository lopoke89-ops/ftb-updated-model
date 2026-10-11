"""Verify and upload an existing NBA season library as one immutable release bundle."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from archive_store import ReleaseArchive, read


def seed(library, output):
    library, output = Path(library).resolve(), Path(output).resolve()
    manifest = read(library/'manifest.json')
    documents = manifest['documents']
    for doc in documents:
        path = (library/doc['pdf_path']).resolve()
        if not path.is_relative_to(library) or hashlib.sha256(path.read_bytes()).hexdigest()!=doc['sha256']:
            raise ValueError('Archived PDF failed original hash verification')
        if doc['verification_status']!='verified':
            raise ValueError('Unverified document in season archive')
    season = manifest['summary']['season']
    output.mkdir(parents=True,exist_ok=True)
    target = output/(season+'-gamebooks.zip')
    names = {'gamebooks.sqlite','manifest.json','SUMMARY.json','README.md','SOURCE_NOTES.md',
             'source_policy.json','library_verification.json','official_vs_prior_staged_differences.json'}
    files = sorted(p for p in library.rglob('*') if p.is_file() and
                   (p.name in names and p.parent==library or p.relative_to(library).parts[0] in ('pdf','records') or
                    p.is_relative_to(library/'text/final_boxes')))
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:
            archive.write(path,path.relative_to(library).as_posix())
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    final = output/(season+'-gamebooks-'+checksum+'.zip')
    target.replace(final)
    url = ReleaseArchive().upload(final,'nba-'+season+'-archive','NBA '+season+' verified gamebook archive')
    result = {'season':season,'pdfs':len(documents),'bytes':final.stat().st_size,'sha256':checksum,'url':url}
    print(json.dumps(result))
    (output/'archive_receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    seed(args.library,args.output)
