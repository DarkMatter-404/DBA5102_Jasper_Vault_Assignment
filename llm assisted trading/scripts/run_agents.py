"""Run actual API research when credentials are provided; preserve offline labels."""
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from etl.agents import ChatClient,process_records

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--limit',type=int,default=50,help='Maximum source cards, two API requests each')
    a=p.parse_args();src=Path(a.input);dest=Path(a.output)
    if src.resolve()==dest.resolve() or dest.exists():p.error('Choose a new output file to preserve provenance.')
    records=[json.loads(l) for l in src.read_text().splitlines() if l.strip()][:a.limit]
    dest.parent.mkdir(parents=True,exist_ok=True)
    rows=process_records(records,ChatClient(),ROOT/'prompts',dest.with_suffix('.api_log.jsonl'))
    dest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    print(json.dumps({'processed':len(rows),'admitted':sum(r['review']['admit'] for r in rows),'output':str(dest)}))
