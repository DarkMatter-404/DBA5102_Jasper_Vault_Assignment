"""Research records, explicit availability clocks, and deduplicated event context."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ARMS = ['market_only','keyword_rules','single_research','verified_research']
CATEGORIES = {'inflation','labor','monetary_policy','regulation','security','exchange_operations','none'}

def keyword_category(text):
    s = text.lower()
    if any(w in s for w in ['hack','attack','exploit','breach']): return 'security'
    if any(w in s for w in ['consumer price','cpi','producer price','ppi']): return 'inflation'
    if any(w in s for w in ['employment situation','payroll']): return 'labor'
    if any(w in s for w in ['fomc','federal reserve','monetary policy']): return 'monetary_policy'
    if any(w in s for w in ['sec ','cftc','regulation','securities laws']): return 'regulation'
    if any(w in s for w in ['exchange','withdrawal','bithumb']): return 'exchange_operations'
    return 'none'

class Events:
    def __init__(self, path, clock='publication_proxy'):
        self.records = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        if len({r['source_id'] for r in self.records})!=len(self.records):
            raise ValueError('Source IDs must be unique; retain duplicates as revisions, not extra evidence.')
        for r in self.records:
            clocks=[pd.Timestamp(r[k]) for k in ['published_at','proxy_available_at','collected_at','processed_at']]
            if any(c.tzinfo is None for c in clocks):raise ValueError('Evidence clocks require timezones.')
            if clocks[1]<clocks[0]+pd.Timedelta(minutes=5):raise ValueError('Evidence processing delay missing.')
            if clocks[3]<clocks[2]:raise ValueError('Processing cannot precede collection.')
        self.clock = clock
        self.by_arm = {}
        for arm in ARMS[1:]:
            rows=[]
            for r in self.records:
                label = r['research'] if arm=='single_research' else r['review']
                cat = keyword_category(r['title']+' '+r['source_fact']) if arm=='keyword_rules' else label['category']
                if cat not in CATEGORIES: raise ValueError('Unknown category')
                if arm=='verified_research' and (not label['admit'] or r['source_kind']!='primary'): continue
                if cat=='none': continue
                proxy = pd.Timestamp(r['proxy_available_at'])
                actual = max(pd.Timestamp(r['collected_at']),pd.Timestamp(r['processed_at']))
                at = max(proxy,actual) if clock=='observed' else proxy
                rows.append({'at':at.value, 'event_id':r['event_id'], 'source_id':r['source_id'], 'category':cat})
            rows=sorted(rows,key=lambda r:r['at'])
            if arm=='verified_research':
                seen=set(); unique=[]
                for r in rows:
                    if r['event_id'] not in seen:
                        unique.append(r); seen.add(r['event_id'])
                rows=unique
            self.by_arm[arm] = rows

    def context(self, t, arm):
        if arm=='market_only': return None
        now=pd.Timestamp(t).value
        rows=[r for r in self.by_arm[arm] if 0 <= (now-r['at'])/3.6e12 <= 6]
        if not rows: return None
        # Latest distinct episode; one major context per quote, no duplicate-count boost.
        r=rows[-1]
        return {**r,'strength':float(2**(-(now-r['at'])/3.6e12/2))}

    def archive_labels(self, times, arm):
        cats=[]; ids=[]
        for t in times:
            c=self.context(pd.Timestamp(t,tz='UTC'),arm)
            cats.append(c['category'] if c else 'none'); ids.append(c['event_id'] if c else '')
        return np.array(cats),np.array(ids)

    def audit(self):
        return {'source_records':len(self.records), 'unique_events':len({r['event_id'] for r in self.records}),
            'verified_admitted_sources':sum(r['review']['admit'] for r in self.records),
            'verified_rejected_sources':sum(not r['review']['admit'] for r in self.records),
            'label_provenance':'Two recorded passes in an interactive assistant session, not independent external API calls.',
            'clock':self.clock, 'coverage':'Purposive sample; macro release occurrences plus selected crypto announcements.'}
