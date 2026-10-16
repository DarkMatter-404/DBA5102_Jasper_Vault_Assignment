"""Optional API-assisted research and verification, with immutable source clocks.

This adapter is NOT invoked by the offline study. Compatible with a provider
supporting /chat/completions and JSON object responses. No credentials are saved.
"""
import json,os,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from .events import CATEGORIES

def now():return datetime.now(timezone.utc).isoformat()

class ChatClient:
    def __init__(self):
        self.base=os.environ.get('LLM_BASE_URL','https://api.openai.com/v1').rstrip('/')
        self.key=os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY')
        self.model=os.environ.get('LLM_MODEL')
        self.verifier=os.environ.get('LLM_VERIFIER_MODEL',self.model)
        if not self.key or not self.model:raise RuntimeError('Set LLM_API_KEY and LLM_MODEL before an API research run.')
        if urlsplit(self.base).scheme!='https':raise ValueError('API endpoint must use HTTPS.')

    def call(self,prompt,payload,model):
        body={'model':model,'messages':[{'role':'system','content':prompt},
            {'role':'user','content':json.dumps(payload)}],'response_format':{'type':'json_object'}}
        req=Request(self.base+'/chat/completions',data=json.dumps(body).encode(),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        start=time.monotonic()
        with urlopen(req,timeout=60) as response:raw=json.load(response)
        result=json.loads(raw['choices'][0]['message']['content'])
        return result,{'model':raw.get('model',model),'usage':raw.get('usage'),
                       'latency_seconds':time.monotonic()-start,'response_id':raw.get('id')}

def validate_label(result,review=False):
    fields={'category','reason','admit'} if review else {'category','reason'}
    if set(result)!=fields or result.get('category') not in CATEGORIES or not isinstance(result.get('reason'),str):
        raise ValueError('Research response failed schema validation.')
    if review and not isinstance(result['admit'],bool):raise ValueError('admit must be boolean')
    if len(result['reason'])>1200:raise ValueError('Unbounded research response')
    return result

def process_records(records,client,prompt_dir,log_path):
    research_prompt=(Path(prompt_dir)/'researcher.txt').read_text()
    verify_prompt=(Path(prompt_dir)/'verifier.txt').read_text()
    output=[]; history=[]
    with Path(log_path).open('w') as log:
        for source in sorted(records,key=lambda r:r['proxy_available_at']):
            # Labels and all quantitative outcomes are excluded from model input.
            keys=['source_id','event_id','title','url','source_fact','published_at','event_date','proxy_available_at','collected_at','source_kind','clock_basis']
            card={k:source[k] for k in keys}
            evidence_hash=hashlib.sha256(json.dumps(card,sort_keys=True).encode()).hexdigest()
            row=dict(source); calls=[]
            try:
                analyst,meta=client.call(research_prompt,card,client.model)
                row['research']=validate_label(analyst); calls.append({'role':'researcher',**meta,'output':analyst})
                prior=[h for h in history if h['event_id']==card['event_id']]
                review,meta=client.call(verify_prompt,{'source':card,'analyst':analyst,'earlier_same_episode':prior},client.verifier)
                row['review']=validate_label(review,True);calls.append({'role':'verifier',**meta,'output':review})
                if card['source_kind']!='primary':
                    row['review']={**review,'admit':False,'reason':'Deterministic source gate: primary evidence required. '+review['reason']}
            except Exception as exc:
                # Fail closed. Do not spill headers, keys or entire response bodies.
                row['research']={'category':'none','reason':'API/schema failure; no signal.'}
                row['review']={'category':'none','admit':False,'reason':'API/schema failure; no signal.'}
                calls.append({'error_type':type(exc).__name__})
            row['processed_at']=now();row['label_provenance']='external_api_two_pass'
            row['input_sha256']=evidence_hash
            log.write(json.dumps({'source_id':card['source_id'],'at':row['processed_at'],'input_sha256':evidence_hash,
                'research_prompt_sha256':hashlib.sha256(research_prompt.encode()).hexdigest(),
                'verifier_prompt_sha256':hashlib.sha256(verify_prompt.encode()).hexdigest(),'calls':calls})+'\n')
            output.append(row);history.append({k:card[k] for k in ['event_id','source_id','proxy_available_at']})
    return output
