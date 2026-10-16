"""Rebuild the disclosed, manually recorded assistant research replay.

This script does NOT call an LLM. The labels were recorded in the authoring
session before calculating forecast scores. It encodes those labels exactly.
"""
import json, hashlib
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
RECEIVED='2026-10-16T02:55:00Z'
ROWS=[]
def add(event_id,title,url,fact,when,category,review_category=None,admit=True,reason='',clock='explicit_publication',source_kind='primary',event_date=None):
    if len(when)==10:
        # Date-only: wait until end of local source day; conservative US Eastern.
        published=datetime.fromisoformat(when).replace(tzinfo=ZoneInfo('America/New_York'))
        proxy=(published+timedelta(days=1,minutes=5)).astimezone(timezone.utc)
        clock='date_only_end_of_eastern_day'
    else:
        published=datetime.fromisoformat(when.replace('Z','+00:00'))
        proxy=published+timedelta(minutes=5)
    source_id='s'+hashlib.sha256((url+title+when).encode()).hexdigest()[:12]
    ROWS.append({'source_id':source_id,'event_id':event_id,'title':title,'url':url,'source_fact':fact,
        'published_at':published.isoformat(),'event_date':event_date or when[:10],
        'proxy_available_at':proxy.isoformat(),'collected_at':RECEIVED,'processed_at':RECEIVED,
        'clock_basis':clock,'source_kind':source_kind,'label_provenance':'recorded_interactive_assistant_session',
        'research':{'category':category,'reason':'Classify the source fact by its economic transmission channel; no directional probability assigned.'},
        'review':{'category':review_category or category,'admit':admit,'reason':reason or 'Primary dated source; BTC-relevant broad market context. No surprise magnitude inferred.'},
        'input_sha256':hashlib.sha256((title+'\n'+fact).encode()).hexdigest()})

calendar='https://www.bls.gov/schedule/2026/home.htm'
# Only occurrence and clock are extracted from the official calendar. No
# consensus surprise, payroll value or inflation direction is manufactured.
series=[('cpi','Consumer Price Index','inflation',
    ['01-13','02-13','03-11','04-10','05-12','06-10','07-14','08-12','09-11','10-14']),
    ('jobs','Employment Situation','labor',
    ['01-09','02-11','03-06','04-03','05-08','06-05','07-02','08-07','09-04','10-02']),
    ('ppi','Producer Price Index','inflation',
    ['01-14','01-30','02-27','03-18','04-14','05-13','06-11','07-15','08-13','09-10'])]
for tag,title,cat,dates in series:
    for date in dates:
        dt=datetime.fromisoformat('2026-'+date+'T08:30:00').replace(tzinfo=ZoneInfo('America/New_York'))
        add(tag+'-'+date,title+' release',calendar,'Official calendar lists this US data release at 08:30 Eastern.',
            dt.isoformat(),cat,clock='official_calendar_occurrence_proxy',
            reason='Calendar confirms release timing; use only AFTER release plus five minutes. No archived receipt or release surprise is claimed.')

for date,decision in [('01-28','held'),('03-18','held'),('04-29','held'),('06-17','held'),('07-29','held'),('09-16','raised')]:
    dt=datetime.fromisoformat('2026-'+date+'T14:00:00').replace(tzinfo=ZoneInfo('America/New_York'))
    url='https://www.federalreserve.gov/newsevents/pressreleases/monetary2026'+date.replace('-','')+'a.htm'
    add('fomc-'+date,'Federal Reserve FOMC policy statement',url,
        f'The committee {decision} its policy rate target; the statement was released at 14:00 Eastern.',dt.isoformat(),'monetary_policy')

add('crypto-regulatory-meeting-jan','SEC and CFTC announce a crypto harmonization event',
    'https://www.sec.gov/newsroom/press-releases/2026-13',
    'Announcement of a future inter-agency discussion; the page was updated January 26.',
    '2026-01-26','regulation',admit=False,
    reason='Meeting advertisement, not a substantive rule change. Updated page cannot be backdated to January 22.')
add('crypto-regulatory-meeting-jan','CFTC and SEC announce a crypto harmonization event',
    'https://www.cftc.gov/PressRoom/PressReleases/9170-26',
    'The agencies advertised a forthcoming joint discussion on crypto policy.',
    '2026-01-22','regulation',admit=False,reason='Same meeting episode as SEC notice; promotional schedule rather than a new regulatory decision.')
add('crypto-taxonomy-mar17','SEC clarifies securities laws for crypto assets',
    'https://www.sec.gov/newsroom/press-releases/2026-30-sec-clarifies-application-federal-securities-laws-crypto-assets',
    'SEC issued an interpretation of crypto-asset securities treatment, with CFTC participation.',
    '2026-03-17','regulation',reason='Substantive primary regulatory interpretation; date-only clock delays use until next morning UTC.')
add('crypto-regulation-aug18','SEC proposes Regulation Crypto Assets',
    'https://www.sec.gov/newsroom/press-releases/2026-76-sec-proposes-new-regulation-crypto-assets',
    'SEC proposed a crypto offering framework and conditional exemptions; these were proposals, not final rules.',
    '2026-08-18','regulation',reason='Primary proposal; no assumption of enactment or price direction.')
add('drift-april-incident','Drift incident recovery and security update',
    'https://www.drift.trade/updates/incident-recovery-update-april-16-2026-now',
    'Drift outlined recovery plans after an earlier exploit. The currently retrieved page includes a July 7 withdrawal update.',
    '2026-07-07','security',review_category='exchange_operations',admit=False,
    reason='Mutable recovery page contains later edits; not fresh BTC security news. Do not backdate current text to April 1 or April 16.',event_date='2026-04-01')
add('drift-relaunch-june','Drift recovery update titled June 3',
    'https://www.drift.trade/updates/drift-recovery-update-june-3-2026',
    'A relaunch progress report described risk-system work and a recovery pool; displayed publication date is June 4.',
    '2026-06-04','exchange_operations',admit=False,
    reason='Routine progress on a Solana venue, not a newly evidenced broad BTC shock. Use displayed publication date rather than title date.')
add('bithumb-feb-error','Bithumb bitcoin allocation error was not an external hack',
    'https://www.theguardian.com/world/2026/feb/10/bithumb-korean-crypto-exchange-sent-bitcoin-mistake',
    'A report describes an earlier mistaken promotional bitcoin credit and subsequent recovery efforts.',
    '2026-02-10T04:26:12Z','exchange_operations',admit=False,
    reason='Retrospective secondary report of February 6 incident; cannot treat a days-old event as a new six-hour BTC shock.',source_kind='secondary',event_date='2026-02-06')
add('drift-april-incident','Drift attack and withdrawal suspension reported',
    'https://www.tomshardware.com/tech-industry/cryptocurrency/crypto-platform-drift-suffers-from-hack-suspected-to-total-usd270-million-firm-goes-into-damage-control-mode-suspends-deposits-and-withdrawals',
    'The April 3 report relays a Drift announcement of an April 1 attack and deposit and withdrawal suspension.',
    '2026-04-03T10:50:38Z','security',admit=False,
    reason='Delayed secondary report; immediate timing and broad BTC relevance are unverified.',source_kind='secondary',event_date='2026-04-01')
ROWS.sort(key=lambda x:(x['proxy_available_at'],x['source_id']))
out=ROOT/'data/events/recorded_events.jsonl'
out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ROWS))
print(json.dumps({'records':len(ROWS),'events':len({r['event_id'] for r in ROWS}),
                  'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
