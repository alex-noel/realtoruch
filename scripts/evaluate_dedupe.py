#!/usr/bin/env python3
"""Deterministic, synthetic-only evaluation of the production dedupe path."""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / 'backend/tests/fixtures/dedupe/pairs.jsonl'
EXPECTED_FAMILIES = {
    'same_home_repost': 'development', 'morizon_gratka': 'development',
    'address_image': 'development', 'resized_image_url': 'holdout',
    'shared_agency_phone': 'holdout', 'unit_floor_conflict': 'holdout',
    'stock_photo': 'development', 'missing_address_location': 'development',
    'city_conflict': 'holdout', 'room_area_boundary': 'holdout',
    'building_no_unit': 'holdout',
}
LABELS = {'same_home', 'different_home', 'ambiguous'}


def read_dataset(path):
    rows=[]
    for lineno, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row=json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'line {lineno}: invalid JSON: {exc}') from exc
        rows.append(row)
    validate_dataset(rows)
    return rows


def validate_dataset(rows):
    seen=set(); family_partitions=defaultdict(set); counts=Counter()
    required={'id','label','rationale','scenario_family','partition','provenance','candidate','incoming','sources','expected_auto_merge'}
    for row in rows:
        pid=row.get('id','<missing id>')
        missing=required-row.keys()
        if missing: raise ValueError(f'{pid}: missing fields {sorted(missing)}')
        if pid in seen: raise ValueError(f'{pid}: duplicate pair ID')
        seen.add(pid)
        if row['label'] not in LABELS: raise ValueError(f'{pid}: invalid label {row["label"]!r}')
        if not isinstance(row['rationale'],str) or not row['rationale'].strip(): raise ValueError(f'{pid}: missing rationale')
        fam=row['scenario_family']; part=row['partition']
        if fam not in EXPECTED_FAMILIES: raise ValueError(f'{pid}: unknown scenario family {fam!r}')
        if part not in ('development','holdout'): raise ValueError(f'{pid}: invalid partition {part!r}')
        if part != EXPECTED_FAMILIES[fam]: raise ValueError(f'{pid}: family {fam!r} belongs to {EXPECTED_FAMILIES[fam]}, not {part}')
        family_partitions[fam].add(part); counts[row['label']]+=1
        if row['expected_auto_merge'] is not {'same_home':True,'different_home':False,'ambiguous':None}[row['label']]:
            raise ValueError(f'{pid}: expected_auto_merge conflicts with authored label')
        if 'phone' in json.dumps(row).lower():
            # Phone hash is allowed; raw phone field/value is not.
            if 'phone_hash' not in json.dumps(row): raise ValueError(f'{pid}: unexpected contact data')
        if any(key in row.get('incoming',{}) for key in ('phone','email','account_email')):
            raise ValueError(f'{pid}: raw personal contact field present')
    if len(rows)<200 or counts['same_home']<80 or counts['different_home']<80 or counts['ambiguous']<40:
        raise ValueError(f'insufficient dataset: {len(rows)} total, label counts={dict(counts)}')
    for family, parts in family_partitions.items():
        if len(parts)!=1: raise ValueError(f'{family}: scenario family leaks across partitions')
    if set(family_partitions)!=set(EXPECTED_FAMILIES): raise ValueError('required scenario family missing')
    return {'total':len(rows),'labels':dict(counts),'families':{k:sorted(v)[0] for k,v in family_partitions.items()}}


def run_match(row, matcher=None):
    if matcher is None:
        from realtoruch.dedupe import matching_property
        matcher=matching_property
    c=row['candidate']; incoming=row['incoming']
    candidate=SimpleNamespace(**c)
    sources=[SimpleNamespace(source=s['source'],phone_hash=s.get('phone_hash'),data=s['data']) for s in row['sources']]
    return matcher(candidate,incoming,sources)


def evaluate(rows, matcher=None):
    matrix={label:{'auto_merge':0,'no_merge':0} for label in ('same_home','different_home','ambiguous')}
    by_family=defaultdict(lambda:{'count':0,'auto_merge':0,'failures':[]})
    failures=[]
    prediction_ids=set()
    for row in rows:
        # A completed match/no-match decision is required for every row; exceptions
        # propagate and leave no report rather than quietly shrinking denominators.
        prediction=run_match(row,matcher)
        prediction_ids.add(row['id'])
        matched=prediction is not None
        label=row['label']; family=row['scenario_family']
        matrix[label]['auto_merge' if matched else 'no_merge']+=1
        metric=by_family[family]; metric['count']+=1; metric['auto_merge']+=int(matched)
        incorrect=(label=='same_home' and not matched) or (label=='different_home' and matched) or (label=='ambiguous' and matched)
        if incorrect:
            failures.append(row['id']); metric['failures'].append(row['id'])
    tp=matrix['same_home']['auto_merge']; fn=matrix['same_home']['no_merge']
    fp=matrix['different_home']['auto_merge']; tn=matrix['different_home']['no_merge']
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else 0.0
    if len(prediction_ids) != len(rows):
        raise ValueError(f'prediction coverage incomplete: {len(prediction_ids)}/{len(rows)}')
    return {'prediction_coverage':{'predicted':len(prediction_ids),'expected':len(rows),'complete':True},
            'confusion_known':{'tp':tp,'fp':fp,'tn':tn,'fn':fn},'precision':precision,'recall':recall,
            'ambiguous_auto_merge_count':matrix['ambiguous']['auto_merge'],'per_label':matrix,
            'per_scenario':{k:dict(v) for k,v in sorted(by_family.items())},'failure_ids':sorted(failures)}


def sequence_evaluation():
    """Exercise ingest() and matching_property() via actual SQLite-backed ingestion."""
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from realtoruch.db import Base
    from realtoruch.ingest import ingest
    from realtoruch.models import Listing, AlertEvent
    from realtoruch.schemas import RawListing
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(engine,expire_on_commit=False)() as session:
        common=dict(url='https://synthetic.example.test/listing',title='Synthetic rental home',description='Synthetic evaluation record',city='Warszawa',district='Test',region='Synthetic',address='Sequence Street 10',lat=52.2,lon=21.0,area_m2=54,rooms=2,floor=2,rent_pln=4000,fees_pln=None,deposit_pln=None,commission_pln=None,advertiser_type='private',property_type='apartment',phone_hash='a'*64,images=['https://images.example.test/sequence/home.jpg?asset=seq1'])
        def raw(source,eid,**kw): return RawListing(source=source,external_id=eid,**(common|kw))
        a=ingest(session,raw('otodom','seq-a'))
        b=ingest(session,raw('gratka','seq-b'))
        c=ingest(session,raw('olx','seq-c',address='Sequence Street 10/8',floor=8))
        listing_count=session.scalar(select(func.count()).select_from(Listing))
        alert_events=session.scalar(select(func.count()).select_from(AlertEvent))
        result={'steps':[{'name':'first source','status':a['status']},{'name':'same-home repost','status':b['status']},{'name':'conflicting unit/floor','status':c['status']}],
                'canonical_count':listing_count,'expected_canonical_count':2,'canonical_count_correct':listing_count==2,
                'alert_event_count':alert_events,'expected_alert_event_count':2,'alert_suppressed_for_repost':a['listing_id']==b['listing_id'] and alert_events==2,
                'identity_outcomes':{'repost_same_canonical':a['listing_id']==b['listing_id'],'distinct_unit_separate':c['listing_id']!=a['listing_id']}}
    engine.dispose(); return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=DEFAULT_DATASET)
    parser.add_argument('--partition',choices=('all','development','holdout'),default='all')
    parser.add_argument('--output',type=Path,help='Write JSON report to path; default stdout')
    args=parser.parse_args()
    rows=read_dataset(args.dataset)
    original_count=len(rows)
    if args.partition!='all': rows=[r for r in rows if r['partition']==args.partition]
    dataset_hash=hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    code_sha=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True).stdout.strip() or 'unavailable'
    report={'report_version':1,'run_id':datetime.now(timezone.utc).strftime('T09-%Y%m%dT%H%M%SZ'),'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'dataset_path':str(args.dataset.relative_to(ROOT) if args.dataset.is_relative_to(ROOT) else args.dataset),'dataset_sha256':dataset_hash,'dataset_pair_count':original_count,'evaluated_pair_count':len(rows),
            'code_git_sha':code_sha,'evaluator_sha256':script_hash,'parameters':{'partition':args.partition,'matcher':'realtoruch.dedupe.matching_property','thresholds':'production defaults; no tuning','seed':None},
            'synthetic_only':True,'real_market_accuracy_claimed':False,'validation':validate_dataset(read_dataset(args.dataset)),'metrics':evaluate(rows),
            'partition_metrics':{part:evaluate([r for r in read_dataset(args.dataset) if r['partition']==part]) for part in ('development','holdout')}}
    if args.partition=='all': report['ingestion_sequence']=sequence_evaluation()
    rendered=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output: args.output.write_text(rendered)
    else: print(rendered,end='')
    return 0
if __name__=='__main__': sys.exit(main())
