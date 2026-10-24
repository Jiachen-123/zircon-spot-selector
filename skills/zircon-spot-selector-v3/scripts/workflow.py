#!/usr/bin/env python3
"""Reviewed candidates, evidence-bound revisions, atomic recovery and synchronized exports.
No image classifier. A recorded review must come from actual raw-image inspection.
"""
from __future__ import annotations
import argparse,copy,csv,datetime,hashlib,json,math,os,tempfile
from pathlib import Path
import pdf_engine as engine

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

def transform(matrix,point):
    if len(matrix)!=3 or any(len(row)!=3 for row in matrix):raise ValueError('3x3 affine matrix required')
    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for row in matrix for v in row):raise ValueError('finite transform required')
    if matrix[2]!=[0,0,1]:raise ValueError('projective mapping unsupported for precise circles')
    if abs(matrix[0][0]*matrix[1][1]-matrix[0][1]*matrix[1][0])<1e-12:raise ValueError('singular transform')
    return [sum(row[i]*[*point,1][i] for i in range(3)) for row in matrix[:2]]

def ellipse_rect(matrix,center,diameter):
    c=transform(matrix,center);rx,ry=[v/2 for v in diameter]
    # General rotated ellipse would require a path, not an axis-aligned /Circle.
    covariance=matrix[0][0]*matrix[1][0]*rx*rx+matrix[0][1]*matrix[1][1]*ry*ry
    if abs(covariance)>1e-8:raise ValueError('rotated ellipse/shear needs reviewed path export, not Circle')
    ex=math.hypot(matrix[0][0]*rx,matrix[0][1]*ry);ey=math.hypot(matrix[1][0]*rx,matrix[1][1]*ry)
    return [c[0]-ex,c[1]-ey,c[0]+ex,c[1]+ey]

def load_registry(plan,base):
    record=plan.get('defect_registry')
    if not record or not record.get('path') or not record.get('sha256'):raise ValueError('shared defect registry and hash required, including explicit empty registry')
    path=engine.resolve(base,record['path'])
    if file_hash(path)!=record['sha256']:raise ValueError('defect registry changed; reconcile evidence and rereview')
    registry=json.loads(path.read_text('utf-8'))
    if registry.get('sample_id')!=plan.get('sample_id'):raise ValueError('registry belongs to another sample')
    return registry

def footprint_fingerprint(plan,spot,base):
    field=next(f for f in plan['fields'] if f['id']==spot['field'])
    assets={'source_pdf':file_hash(engine.resolve(base,plan['source_pdf']))}
    if field.get('cl_image'):assets['cl_image']=file_hash(engine.resolve(base,field['cl_image']))
    for mode,panel in spot.get('panels',{}).items():assets[mode]=file_hash(engine.resolve(base,panel['path']))
    for mode,panel in spot.get('defect_panels',{}).items():assets['defects_'+mode]=file_hash(engine.resolve(base,panel['path']))
    return digest({'sample':plan.get('sample_id'),'objective':plan.get('objective'),'beam':plan['beam_diameter_um'],'registry':plan.get('defect_registry'),'field':field,'spot':{k:v for k,v in spot.items() if k not in ['review','history'] and not k.startswith('_')},'assets':assets})

def record_review(plan,key,base,reviewer,basis):
    if not reviewer.strip() or not basis.strip():raise ValueError('reviewer and actual image-review basis required')
    spot=next(s for s in plan['spots'] if s['key']==key)
    spot['review']={'fingerprint':footprint_fingerprint(plan,spot,base),'reviewer':reviewer,'basis':basis,'time':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    return plan

def prepare(plan,base):
    p=copy.deepcopy(plan)
    if not p.get('sample_id'):raise ValueError('explicit sample_id required')
    registry=load_registry(p,base);by={f['id']:f for f in p['fields']}
    for feature in registry['features']:
        if feature.get('field') not in by or not feature.get('source_evidence'):raise ValueError('registry feature needs valid field and source evidence')
    from PIL import Image
    for field in p['fields']:
        if field.get('cl_image'):
            with Image.open(engine.resolve(base,field['cl_image'])) as native:
                if list(native.size)!=field['image_size_px']:raise ValueError('declared native image size differs from actual image')
        for name in ['scale','scale_y']:
            if field.get(name):
                w,h=field['image_size_px']
                if any(not(0<=pt[0]<=w and 0<=pt[1]<=h) for pt in field[name]['endpoints_px']):raise ValueError('scale endpoints outside native image')
    if not p.get('objective'):
        if p.get('objective_status')!='pending' or p['count_basis']!='candidates':raise ValueError('unknown objective must explicitly remain pending')
        p['objective']='pending_not_inferred'
        if any(s.get('manual_acceptance') for s in p['spots']):raise ValueError('unknown objective cannot be accepted')
    all_original={s['key']:s for s in plan['spots']}
    for spot in p['spots']:
        if not spot.get('include_in_main'):continue
        if spot.get('sample_id')!=p['sample_id']:raise ValueError('cross-sample spot contamination')
        original=all_original[spot['key']]
        review=original.get('review',{})
        if review.get('fingerprint')!=footprint_fingerprint(plan,original,base):raise ValueError('missing/stale whole-footprint review: '+spot['key'])
        if not review.get('basis') or not review.get('reviewer'):raise ValueError('review evidence required')
        if spot.get('image_judgment')=='uncertain' and not spot.get('resolution_attempts'):raise ValueError('uncertain candidate needs actual move/domain/replacement investigation record')
        if spot.get('positioning')=='sufficient' and not spot.get('positioning_evidence'):raise ValueError('sufficient positioning needs independent local evidence')
        if spot.get('image_judgment')=='suitable' and spot.get('unresolved_image_issues'):raise ValueError('unresolved image issue cannot be relabeled suitable')
        field=by[spot['field']]
        spot['obstacles']=spot.get('obstacles',[])+[d for d in registry['features'] if d['field']==spot['field']]
        if field.get('pdf_transform'):ellipse_rect(field['pdf_transform'],spot['xy_px'],[p['beam_diameter_um']*s for s in engine.scales(field)])
    validated,main,summary=engine.validate(p,base)
    if any(s['positioning']=='sufficient' and s['_unknown_terms'] for s in main):raise ValueError('unknown positioning budget cannot be sufficient')
    # Stable grain IDs are sample scoped and span repeated views. Independent domains
    # on one grain need an explicit strategy; overlapping positions are never extra points.
    for i,s in enumerate(main):
        f=by[s['field']]
        for t in main[:i]:
            g=by[t['field']]
            if s['field']==t['field']:continue
            if f.get('physical_frame') and f.get('physical_frame')==g.get('physical_frame'):
                if not f.get('native_to_frame_um') or not g.get('native_to_frame_um'):raise ValueError('shared physical frame needs explicit native-to-um transforms')
                a=transform(f['native_to_frame_um'],s['xy_px']);b=transform(g['native_to_frame_um'],t['xy_px'])
                if math.dist(a,b)<p['beam_diameter_um']:raise ValueError('duplicate/overlapping spot across views')
    minimum=p.get('minimum_count')
    if minimum is not None and (not isinstance(minimum,int) or isinstance(minimum,bool) or minimum<1):raise ValueError('invalid minimum count')
    summary.update(sample_id=p['sample_id'],minimum_count=minimum,minimum_shortfall=None if minimum is None else max(0,minimum-len(main)),objective_pending=plan.get('objective_status')=='pending',expert_accuracy_validated=False)
    return validated,main,summary

def checkpoint(path,plan,base,next_step):
    """One atomic snapshot contains plan and hash-linked events; no torn two-file save."""
    path=Path(path);history=[]
    if path.exists():
        old=resume(path);history=old['history']
        if old['plan']['sample_id']!=plan['sample_id']:raise ValueError('checkpoint sample mismatch')
    assets={str(engine.resolve(base,plan['source_pdf'])):file_hash(engine.resolve(base,plan['source_pdf']))}
    for field in plan['fields']:
        if field.get('cl_image'):assets[str(engine.resolve(base,field['cl_image']))]=file_hash(engine.resolve(base,field['cl_image']))
    for s in plan['spots']:
        for panel in s.get('panels',{}).values():assets[str(engine.resolve(base,panel['path']))]=file_hash(engine.resolve(base,panel['path']))
        for panel in s.get('defect_panels',{}).values():assets[str(engine.resolve(base,panel['path']))]=file_hash(engine.resolve(base,panel['path']))
        if s.get('previous_panel'):assets[str(engine.resolve(base,s['previous_panel']['path']))]=file_hash(engine.resolve(base,s['previous_panel']['path']))
    registry=engine.resolve(base,plan['defect_registry']['path']);assets[str(registry)]=file_hash(registry)
    event={'sequence':len(history)+1,'previous':history[-1]['hash'] if history else None,'plan_hash':digest(plan),'assets_hash':digest(assets),'next_step':next_step,'time':datetime.datetime.now(datetime.timezone.utc).isoformat()};event['hash']=digest(event);history.append(event)
    atomic_json(path,{'plan':plan,'plan_base':str(Path(base).resolve()),'assets':assets,'history':history,'next_step':next_step})

def resume(path):
    saved=json.loads(Path(path).read_text('utf-8'));previous=None
    for i,event in enumerate(saved['history'],1):
        unsigned={k:v for k,v in event.items() if k!='hash'}
        if event['sequence']!=i or event['previous']!=previous or digest(unsigned)!=event['hash']:raise ValueError('checkpoint history corrupt')
        previous=event['hash']
    last=saved['history'][-1]
    if last['plan_hash']!=digest(saved['plan']) or last['assets_hash']!=digest(saved['assets']):raise ValueError('checkpoint snapshot corrupt')
    if any(file_hash(p)!=v for p,v in saved['assets'].items()):raise ValueError('source/evidence changed since checkpoint')
    load_registry(saved['plan'],Path(saved['plan_base']))
    return saved

def absolute_plan(plan,base):
    p=copy.deepcopy(plan);p['source_pdf']=str(engine.resolve(base,p['source_pdf']))
    for f in p['fields']:
        if f.get('cl_image'):f['cl_image']=str(engine.resolve(base,f['cl_image']))
    for s in p['spots']:
        for panel in s.get('panels',{}).values():panel['path']=str(engine.resolve(base,panel['path']))
    return p

def export_bundle(plan_path,destination):
    from atlas import build_atlas
    plan_path=Path(plan_path);raw=json.loads(plan_path.read_text('utf-8'));base=Path(raw.get('_plan_base',plan_path.parent));p,main,summary=prepare(raw,base)
    destination=Path(destination)
    if destination.exists():raise FileExistsError('new version directory required')
    destination.mkdir(parents=True)
    try:
        prepared=destination/'prepared-plan.json';atomic_json(prepared,absolute_plan(p,base))
        export_checks=engine.export(prepared,destination/'spots.pdf',destination/'coordinates.csv',destination/'engine-counts.json')
        checked=engine.verify(prepared,destination/'spots.pdf',destination/'pdf-verification.json',destination/'edit-tests')
        build_atlas(raw,base,destination/'review-atlas.pdf')
        snapshot=copy.deepcopy(raw);snapshot['_plan_base']=str(base.resolve());atomic_json(destination/'reviewed-plan.json',snapshot)
        atomic_json(destination/'state.json',{'sample_id':raw['sample_id'],'spots':main})
        with (destination/'mapping-and-revisions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['number','key','grain','aliases','history']);writer.writeheader()
            for s in main:writer.writerow({'number':s['_number'],'key':s['key'],'grain':s['grain_key'],'aliases':json.dumps(s.get('aliases',{'origin':'new'}),ensure_ascii=False),'history':json.dumps(s.get('history',[]),ensure_ascii=False)})
        summary.update(pdf_checks=checked,source_clone_warnings=export_checks.get('source_clone_warnings',[]),visual_review='required separately; engineering is not geological signoff',artifacts={name:file_hash(destination/name) for name in ['spots.pdf','review-atlas.pdf','coordinates.csv','state.json','mapping-and-revisions.csv']})
        atomic_json(destination/'summary.json',summary)
        checkpoint(destination/'checkpoint.json',raw,base,'Render and inspect all output pages and changed whole footprints; record visual findings.')
        (destination/'progress.md').write_text('Exports and object checks complete. Visual review pending; see summary.json. Resume from checkpoint.json.\n','utf-8')
        return summary
    except Exception as exc:
        atomic_json(destination/'FAILED.json',{'error':str(exc),'complete':False});raise

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    for name in ['check','review','export','checkpoint']:
        c=sub.add_parser(name);c.add_argument('--plan',type=Path,required=True)
        if name=='review':c.add_argument('--key',required=True);c.add_argument('--reviewer',required=True);c.add_argument('--basis',required=True);c.add_argument('--output',type=Path,required=True)
        if name=='export':c.add_argument('--output-dir',type=Path,required=True)
        if name=='checkpoint':c.add_argument('--output',type=Path,required=True);c.add_argument('--next-step',required=True)
    c=sub.add_parser('resume');c.add_argument('--checkpoint',type=Path,required=True)
    args=ap.parse_args()
    if args.command=='resume':print(json.dumps({'next_step':resume(args.checkpoint)['next_step']}));return
    plan=json.loads(args.plan.read_text('utf-8'));base=Path(plan.get('_plan_base',args.plan.parent))
    if args.command=='check':print(json.dumps(prepare(plan,base)[2],ensure_ascii=False))
    elif args.command=='review':
        if args.output.exists():raise FileExistsError('preserve prior plan; use a new review filename')
        atomic_json(args.output,record_review(plan,args.key,base,args.reviewer,args.basis))
    elif args.command=='checkpoint':checkpoint(args.output,plan,base,args.next_step)
    else:print(json.dumps(export_bundle(args.plan,args.output_dir),ensure_ascii=False))

if __name__=='__main__':main()
