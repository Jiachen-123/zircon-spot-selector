#!/usr/bin/env python3
"""Low-level geometry and PDF objects migrated from V2; use workflow.py for V3.
AP/annotation construction adapted from the validated project exporters and v1.
"""
from __future__ import annotations
import argparse,copy,csv,json,math,logging
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from pypdf.generic import (ArrayObject,DictionaryObject,NameObject,FloatObject,
                          NumberObject,TextStringObject,DecodedStreamObject)

def positive(v,name,zero=False):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or (v==0 and not zero):raise ValueError('invalid '+name)
 return float(v)
def xy(v):
 if not isinstance(v,list) or len(v)!=2:raise ValueError('expected x,y')
 return [positive(z,'coordinate',True) for z in v]
def resolve(base,p):return (base/Path(p)).resolve()
def scale(s):
 if s.get('verified') is not True:raise ValueError('scale must be visually verified')
 length=math.dist(*[xy(p) for p in s['endpoints_px']]);return positive(length,'scale bar pixels')/positive(s['value_um'],'scale bar um')
def scales(field):
 sx=scale(field['scale'])
 if field.get('scale_y'):return sx,scale(field['scale_y'])
 if field['scale'].get('isotropic_verified') is not True:raise ValueError('verify isotropic native pixels or provide scale_y')
 return sx,sx
def segment_distance(p,a,b):
 den=sum((b[i]-a[i])**2 for i in [0,1]);t=0 if den==0 else max(0,min(1,sum((p[i]-a[i])*(b[i]-a[i]) for i in [0,1])/den))
 return math.dist(p,[a[i]+t*(b[i]-a[i]) for i in [0,1]])
def inside(p,poly):
 hit=False
 for a,b in zip(poly,poly[1:]+poly[:1]):
  if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:hit=not hit
 return hit
def poly_distance(p,poly):return min(segment_distance(p,a,b) for a,b in zip(poly,poly[1:]+poly[:1]))
def budget(terms):
 if not isinstance(terms,dict) or not terms:return 0.0,['unspecified budget']
 unknown=[k for k,v in terms.items() if v is None];known=sum(positive(v,k,True) for k,v in terms.items() if v is not None)
 return known,unknown
def validate(plan,base=Path('.')):
 p=copy.deepcopy(plan);fields=p['fields'];by={f['id']:f for f in fields}
 if len(by)!=len(fields):raise ValueError('duplicate field id')
 positive(p['beam_diameter_um'],'beam diameter');start=p['numbering_start']
 if isinstance(start,bool) or not isinstance(start,int) or start<1:raise ValueError('invalid numbering start')
 if p['count_basis'] not in ['candidates','accepted']:raise ValueError('explicit count_basis required')
 if not isinstance(p['one_per_grain'],bool):raise ValueError('explicit one_per_grain required')
 if not p.get('objective'):raise ValueError('explicit objective required')
 if 'detrital' in p['objective'] and not p.get('sampling_strategy'):raise ValueError('detrital sampling strategy required')
 target=p.get('target_count')
 if target is not None and (isinstance(target,bool) or not isinstance(target,int) or target<1):raise ValueError('invalid target count')
 for f in fields:
  f['_pxum']=scales(f);f['_size']=xy(f['image_size_px']);rect=f['pdf_rect']
  if len(rect)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in rect) or rect[2]<=rect[0] or rect[3]<=rect[1]:raise ValueError('explicit PDF image rectangle required')
  if not isinstance(f['page'],int) or f['page']<1:raise ValueError('invalid source page')
  if any(z<=0 for z in f['_size']):raise ValueError('invalid image size')
  if f.get('cl_image') and not resolve(base,f['cl_image']).is_file():raise ValueError('CL image missing')
 records=p['spots'];keys=[s['key'] for s in records]
 if len(keys)!=len(set(keys)):raise ValueError('duplicate stable point key')
 main=[s for s in records if s.get('include_in_main')];seen_grains=set();warnings=[]
 for i,s in enumerate(main):
  f=by[s['field']];px,py=f['_pxum'];center=xy(s['xy_px']);s['_number']=start+i;s['_diameter_px']=[p['beam_diameter_um']*px,p['beam_diameter_um']*py]
  if s['image_judgment'] not in ['suitable','uncertain','avoid'] or s['positioning'] not in ['sufficient','pending']:raise ValueError('explicit separate image/position states required')
  if s['image_judgment']=='avoid':raise ValueError('avoid position cannot enter main candidates')
  if s['image_judgment']=='uncertain' and not p.get('include_image_uncertain',False):raise ValueError('image uncertainty needs explicit candidate inclusion authorization')
  if s['coverage']!='full':raise ValueError('partial/unknown coverage must be a separate alternate list')
  if not s.get('observation') or not s.get('pending_issues') or not s.get('domain_review'):raise ValueError('point-specific evidence, domain review and pending issues required')
  if not s.get('identity_basis') or s.get('whole_footprint_reviewed') is not True:raise ValueError('actual same-grain and full footprint review required')
  for mode in p['required_modalities']:
   panel=s.get('panels',{}).get(mode)
   if not panel or not resolve(base,panel['path']).is_file():raise ValueError('missing required raw panel '+mode)
  if s['grain_key'] in seen_grains and p['one_per_grain']:raise ValueError('same grain repeated in one-per-grain plan')
  if s['grain_key'] in seen_grains and not s.get('multi_domain_strategy'):raise ValueError('multiple spots need explicit domain strategy')
  seen_grains.add(s['grain_key']);r=p['beam_diameter_um']/2;u=[center[0]/px,center[1]/py];known,unknown=budget(s.get('uncertainty_um',f.get('uncertainty_um')));s['_known_check_radius_um']=r+known;s['_unknown_terms']=unknown;s['_geometry_warnings']=[]
  rx,ry=[z/2 for z in s['_diameter_px']];width,height=f['_size']
  if center[0]-rx<0 or center[1]-ry<0 or center[0]+rx>width or center[1]+ry>height:raise ValueError('nominal circle outside source image')
  boundary=s.get('interior_polygon_px');interior_ok=False
  if boundary:
   poly=[[v[0]/px,v[1]/py] for v in boundary];dist=poly_distance(u,poly)
   if not inside(u,poly) or dist<r:raise ValueError('nominal footprint outside reviewed grain boundary')
   interior_ok=dist>=r+known
   if not interior_ok:s['_geometry_warnings'].append('known envelope approaches grain edge')
  else:s['_geometry_warnings'].append('no machine-checkable grain boundary; rely on recorded visual review')
  for obstacle in s.get('obstacles',[]):
   if obstacle['kind']=='circle':dist=math.dist(u,[obstacle['center_px'][0]/px,obstacle['center_px'][1]/py])-positive(obstacle['radius_um'],'obstacle radius',True)
   elif obstacle['kind'] in ['polyline','polygon']:
    pts=[[v[0]/px,v[1]/py] for v in obstacle['points_px']]
    if obstacle['kind']=='polygon':dist=-1 if inside(u,pts) else poly_distance(u,pts)
    else:dist=min(segment_distance(u,a,b) for a,b in zip(pts,pts[1:]))-positive(obstacle.get('half_width_um',0),'line half width',True)
   else:raise ValueError('unsupported obstacle')
   if obstacle['certainty']=='confirmed' and dist<=r:raise ValueError('nominal circle intersects confirmed obstacle: '+s['key'])
   if dist<=r+known:s['_geometry_warnings'].append('near '+obstacle['certainty']+' obstacle: '+obstacle.get('description','unlabeled'))
  s['_accepted']=bool(s.get('manual_acceptance'))
  if s['_accepted'] and (s['image_judgment']!='suitable' or s['positioning']!='sufficient' or unknown or not interior_ok or s['_geometry_warnings'] or not s.get('acceptance_basis') or not s.get('positioning_evidence')):raise ValueError('acceptance claims lack image/position/budget/geometry evidence')
  if p['count_basis']=='accepted' and not s['_accepted']:raise ValueError('review candidate cannot count as accepted')
  if unknown or s['positioning']=='pending':warnings.append(s['key']+': positioning/budget pending')
 for i,s in enumerate(main):
  for t in main[:i]:
   if t['field']==s['field']:
    px,py=by[s['field']]['_pxum'];distance=math.hypot((s['xy_px'][0]-t['xy_px'][0])/px,(s['xy_px'][1]-t['xy_px'][1])/py)
    if distance<p['beam_diameter_um']:raise ValueError('duplicate/overlapping nominal spots')
 summary={'candidate_count':len(main),'accepted_count':sum(s['_accepted'] for s in main),'image_suitable':sum(s['image_judgment']=='suitable' for s in main),'image_uncertain':sum(s['image_judgment']=='uncertain' for s in main),'positioning_sufficient':sum(s['positioning']=='sufficient' for s in main),'positioning_pending':sum(s['positioning']=='pending' for s in main),'target_count':target,'shortfall':None if target is None else max(0,target-len(main)),'warnings':warnings,'limits':'Geometry on supplied reviewed features only; not geological validation.'}
 if p.get('require_target_count') and target!=len(main):raise ValueError('actual distinct candidate count differs from required target')
 return p,main,summary

def arr(v):return ArrayObject([FloatObject(float(x)) for x in v])
def obj(d):return DictionaryObject({NameObject(k):v for k,v in d.items()})
def appearance(w,code,width,height,font=False):
 s=DecodedStreamObject();s.update(obj({'/Type':NameObject('/XObject'),'/Subtype':NameObject('/Form'),'/BBox':arr([0,0,width,height])}));resources=DictionaryObject()
 if font:resources[NameObject('/Font')]=obj({'/Helv':w._add_object(obj({'/Type':NameObject('/Font'),'/Subtype':NameObject('/Type1'),'/BaseFont':NameObject('/Helvetica')}))})
 s[NameObject('/Resources')]=resources;s.set_data(code.encode('ascii'));return w._add_object(s)
def annotate(w,page,rect,number,key,state,stroke,font_size,label_rect):
 x0,y0,x1,y1=rect;ww=x1-x0;hh=y1-y0;rx=ww/2;ry=hh/2;k=.5522847498307936
 code=f'q 1 0 0 RG {stroke} w [] 0 d {ww} {ry} m {ww} {ry+k*ry} {rx+k*rx} {hh} {rx} {hh} c {rx-k*rx} {hh} 0 {ry+k*ry} 0 {ry} c 0 {ry-k*ry} {rx-k*rx} 0 {rx} 0 c {rx+k*rx} 0 {ww} {ry-k*ry} {ww} {ry} c S Q'
 a=obj({'/Type':NameObject('/Annot'),'/Subtype':NameObject('/Circle'),'/Rect':arr(rect),'/C':arr([1,0,0]),'/BS':obj({'/W':FloatObject(stroke),'/S':NameObject('/S')}),'/F':NumberObject(4),'/NM':TextStringObject('zircon-v3-circle-'+str(number)),'/Contents':TextStringObject(json.dumps({'key':key,**state},ensure_ascii=False)),'/AP':obj({'/N':appearance(w,code,ww,hh)})});page['/Annots'].append(w._add_object(a))
 l,b,r,t=label_rect;text=str(number);code=f'q 1 0 0 rg BT /Helv {font_size} Tf 2 4 Td ({text}) Tj ET Q'
 a=obj({'/Type':NameObject('/Annot'),'/Subtype':NameObject('/FreeText'),'/Rect':arr(label_rect),'/C':arr([1,0,0]),'/BS':obj({'/W':NumberObject(0)}),'/DA':TextStringObject(f'/Helv {font_size} Tf 1 0 0 rg'),'/F':NumberObject(4),'/NM':TextStringObject('zircon-v3-label-'+text),'/Contents':TextStringObject(text),'/AP':obj({'/N':appearance(w,code,r-l,t-b,True)})});page['/Annots'].append(w._add_object(a))
def mapped_rect(field,center,diameter):
 if field.get('pdf_transform'):
  from workflow import ellipse_rect
  return ellipse_rect(field['pdf_transform'],center,diameter)
 l,b,r,t=field['pdf_rect'];iw,ih=field['_size'];sx=(r-l)/iw;sy=(t-b)/ih;x=l+center[0]*sx;y=t-center[1]*sy;rx=diameter[0]*sx/2;ry=diameter[1]*sy/2
 return [x-rx,y-ry,x+rx,y+ry]
def label_rect(s,f,size,occupied,all_spots):
 if s.get('label_rect_px'):
  l,t,r,b=s['label_rect_px'];pts=[mapped_rect(f,[x,y],[0,0])[:2] for x,y in [(l,t),(l,b),(r,t),(r,b)]];return [min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]
 cr=mapped_rect(f,s['xy_px'],s['_diameter_px']);cx=(cr[0]+cr[2])/2;cy=(cr[1]+cr[3])/2;ww=size*.65*len(str(s['_number']))+6;hh=size+10;opts=[]
 for gap in [6,14,25]:
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
   l=cr[2]+gap if dx>0 else cr[0]-gap-ww if dx<0 else cx-ww/2;b=cr[3]+gap if dy>0 else cr[1]-gap-hh if dy<0 else cy-hh/2;rr=[l,b,l+ww,b+hh]
   if l<f['pdf_rect'][0] or b<f['pdf_rect'][1] or rr[2]>f['pdf_rect'][2] or rr[3]>f['pdf_rect'][3]:continue
   if any(not(rr[2]<v[0] or rr[0]>v[2] or rr[3]<v[1] or rr[1]>v[3]) for v in occupied+all_spots):continue
   opts.append((math.dist([l+ww/2,b+hh/2],[cx,cy]),rr))
 if not opts:raise ValueError('provide an explicit reviewed label_rect_px for '+s['key'])
 return min(opts,key=lambda x:x[0])[1]
def export(plan_path,output,table,report):
 base=plan_path.parent;p,main,summary=validate(json.loads(plan_path.read_text(encoding='utf-8')),base);source=resolve(base,p['source_pdf'])
 if not main:raise ValueError('no main spots to export; deliver the zero-count review report instead')
 targets=[x.resolve() for x in [output,table,report]]
 if len(set(targets))!=3 or any(t in [source,plan_path.resolve()] for t in targets):raise ValueError('source and plan must be preserved; outputs must be distinct')
 if any(x.exists() for x in [output,table,report]):raise ValueError('output already exists; archive or use a new version')
 class CloneMessages(logging.Handler):
  def emit(self,record):self.messages.append(record.getMessage())
 messages=CloneMessages();messages.messages=[];logger=logging.getLogger('pypdf');logger.addHandler(messages)
 try:r=PdfReader(source);w=PdfWriter();w.clone_document_from_reader(r)
 finally:logger.removeHandler(messages)
 summary['source_clone_warnings']=messages.messages
 if any(a.get_object().get('/Subtype')=='/Circle' for pg in r.pages for a in pg.get('/Annots',[])):raise ValueError('use unmarked source PDF; do not duplicate existing circles')
 fields={f['id']:f for f in p['fields']};font=positive(p.get('style',{}).get('font_size_pt',12),'font size');stroke=positive(p.get('style',{}).get('line_width_pt',1.2),'line width');placed={};rows=[]
 for f in fields.values():
  if f['page']>len(w.pages):raise ValueError('page out of source range')
  pg=w.pages[f['page']-1]
  if pg.get('/Rotate',0) or pg.get('/UserUnit',1)!=1:raise ValueError('normalize rotation/UserUnit on a copy and provide verified mapping')
  if f['pdf_rect'][0]<pg.mediabox.left or f['pdf_rect'][1]<pg.mediabox.bottom or f['pdf_rect'][2]>pg.mediabox.right or f['pdf_rect'][3]>pg.mediabox.top:raise ValueError('image mapping outside source page')
 for s in main:
  f=fields[s['field']];pg=w.pages[f['page']-1]
  if '/Annots' not in pg:pg[NameObject('/Annots')]=ArrayObject()
  rect=mapped_rect(f,s['xy_px'],s['_diameter_px']);labels=placed.setdefault(f['page'],[]);obstacles=[mapped_rect(fields[t['field']],t['xy_px'],t['_diameter_px']) for t in main if fields[t['field']]['page']==f['page']];lr=label_rect(s,f,font,labels,obstacles)
  if any(not(lr[2]<v[0] or lr[0]>v[2] or lr[3]<v[1] or lr[1]>v[3]) for v in labels+obstacles):raise ValueError('label overlaps spot or label; revise '+s['key'])
  labels.append(lr);annotate(w,pg,rect,s['_number'],s['key'],{'image':s['image_judgment'],'positioning':s['positioning'],'accepted':s['_accepted'],'diameter_um':p['beam_diameter_um']},stroke,font,lr)
  rows.append({'sample_id':p.get('sample_id',''),'number':s['_number'],'key':s['key'],'grain_key':s['grain_key'],'page':f['page'],'x_px':s['xy_px'][0],'y_px':s['xy_px'][1],'diameter_um':p['beam_diameter_um'],'diameter_x_px':s['_diameter_px'][0],'diameter_y_px':s['_diameter_px'][1],'coverage':s['coverage'],'domain_review':s['domain_review'],'image':s['image_judgment'],'positioning':s['positioning'],'accepted':s['_accepted'],'observation':s['observation'],'pending_issues':s['pending_issues'],'aliases':json.dumps(s.get('aliases',{}),ensure_ascii=False)})
 output.parent.mkdir(parents=True,exist_ok=True);table.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True)
 w.add_metadata({'/Subject':'Review candidates; red solid hollow editable annotations. Statuses and count basis in companion table.'})
 with output.open('wb') as f:w.write(f)
 with table.open('w',encoding='utf-8-sig',newline='') as f:wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
 report.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');return summary
def verify(plan_path,pdf,report,test_dir):
 base=plan_path.parent;p,main,summary=validate(json.loads(plan_path.read_text(encoding='utf-8')),base);r=PdfReader(pdf);src=PdfReader(resolve(base,p['source_pdf']));assert len(r.pages)==len(src.pages);circles={};labels={};fields={f['id']:f for f in p['fields']}
 for i,(pg,sp) in enumerate(zip(r.pages,src.pages),1):
  assert list(pg.mediabox)==list(sp.mediabox)
  assert (pg.get_contents().get_data() if pg.get_contents() else b'')==(sp.get_contents().get_data() if sp.get_contents() else b'')
  for k,v in sp.get('/Resources',{}).get('/XObject',{}).items():assert pg['/Resources']['/XObject'][k].get_object().get_data()==v.get_object().get_data()
  for ref in pg.get('/Annots',[]):
   a=ref.get_object();nm=str(a.get('/NM',''))
   if nm.startswith('zircon-v3-circle-'):
    n=int(nm.rsplit('-',1)[1]);assert n not in circles;circles[n]=(i,a);assert a['/Subtype']=='/Circle' and list(a['/C'])==[1,0,0] and a['/BS']['/S']=='/S' and '/IC' not in a;code=a['/AP']['/N'].get_object().get_data();assert b'[] 0 d' in code and b' S Q' in code
   if nm.startswith('zircon-v3-label-'):
    n=int(nm.rsplit('-',1)[1]);assert n not in labels;labels[n]=(i,a);assert a['/Subtype']=='/FreeText' and a['/Contents']==str(n) and list(a['/C'])==[1,0,0]
 expected={s['_number'] for s in main};assert set(circles)==set(labels)==expected
 for s in main:
  page,a=circles[s['_number']];f=fields[s['field']];assert page==f['page'];assert all(abs(x-y)<1e-5 for x,y in zip(a['/Rect'],mapped_rect(f,s['xy_px'],s['_diameter_px'])))
 test_dir.mkdir(parents=True,exist_ok=True)
 for subtype in ['Circle','FreeText']:
  w=PdfWriter();w.clone_document_from_reader(PdfReader(pdf));a=next(ref.get_object() for pp in w.pages for ref in pp.get('/Annots',[]) if ref.get_object().get('/Subtype')=='/'+subtype)
  if subtype=='Circle':value=[float(x)+2 for x in a['/Rect']];a[NameObject('/Rect')]=arr(value)
  else:
   value='EDIT-TEST';a[NameObject('/Contents')]=TextStringObject(value)
   rect=[float(v) for v in a['/Rect']];width=max(rect[2]-rect[0],100);height=rect[3]-rect[1];a[NameObject('/Rect')]=arr([rect[0],rect[1],rect[0]+width,rect[3]])
   a[NameObject('/AP')]=obj({'/N':appearance(w,'q 1 0 0 rg BT /Helv 10 Tf 2 4 Td (EDIT-TEST) Tj ET Q',width,height,True)})
  op=test_dir/(subtype+'_edit_reopen.pdf')
  with op.open('wb') as f:w.write(f)
  rr=PdfReader(op);changed=next(ref.get_object() for pp in rr.pages for ref in pp.get('/Annots',[]) if ref.get_object().get('/Subtype')=='/'+subtype);assert (list(changed['/Rect']) if subtype=='Circle' else changed['/Contents'])==value
  if subtype=='FreeText':assert b'(EDIT-TEST)' in changed['/AP']['/N'].get_object().get_data()
 result={**summary,'pages':len(r.pages),'source_contents_and_images_preserved':True,'red_solid_hollow_circles':len(circles),'plain_red_labels':len(labels),'circle_and_text_edit_save_reopen':True,'visual_render_review':'required separately'};report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
def main():
 ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
 for name in ['check','export','verify']:
  c=sub.add_parser(name);c.add_argument('--plan',type=Path,required=True);c.add_argument('--report',type=Path,required=True)
  if name=='export':c.add_argument('--output',type=Path,required=True);c.add_argument('--table',type=Path,required=True)
  if name=='verify':c.add_argument('--pdf',type=Path,required=True);c.add_argument('--edit-test-dir',type=Path,required=True)
 a=ap.parse_args()
 if a.command=='check':
  _,_,result=validate(json.loads(a.plan.read_text(encoding='utf-8')),a.plan.parent);a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 elif a.command=='export':result=export(a.plan,a.output,a.table,a.report)
 else:result=verify(a.plan,a.pdf,a.report,a.edit_test_dir)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
