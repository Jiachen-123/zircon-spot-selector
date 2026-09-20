#!/usr/bin/env python3
"""Three-modality zircon spot selection with hard full-footprint exclusion."""
from __future__ import annotations
import argparse, base64, csv, hashlib, io, json, math, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull, QhullError
try:
    import cv2
except ImportError as exc:
    raise SystemExit("OpenCV is required. Install requirements.txt with the Codex bundled Python runtime.") from exc

def load_rgb(path): return np.asarray(Image.open(path).convert("RGB"),dtype=np.uint8)
def gray(rgb): return cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
def disk(r):
    r=max(0,int(r)); y,x=np.ogrid[-r:r+1,-r:r+1]; return x*x+y*y<=r*r
def save_mask(path,mask): Image.fromarray(mask.astype(np.uint8)*255).save(path)
def normalize_u8(a):
    lo,hi=np.percentile(a,[2,98]); return np.clip((a.astype(float)-lo)*255/max(hi-lo,1),0,255).astype(np.uint8)
def prep(rgb):
    g=cv2.createCLAHE(2.0,(8,8)).apply(gray(rgb)); gx=cv2.Sobel(g,cv2.CV_32F,1,0); gy=cv2.Sobel(g,cv2.CV_32F,0,1); return normalize_u8(cv2.magnitude(gx,gy))
def xform(points,h): return cv2.perspectiveTransform(np.asarray(points,np.float32).reshape(-1,1,2),h).reshape(-1,2)

def manual_h(points,name):
    item=points.get(name)
    if not item: raise ValueError(f"manual registration has no {name} points")
    mov=np.asarray(item['moving'],np.float32); fix=np.asarray(item['fixed'],np.float32)
    if mov.shape!=fix.shape or mov.ndim!=2 or mov.shape[1]!=2 or len(mov)<3: raise ValueError(f"{name}: need >=3 paired x,y control points")
    if len(mov)>=4: h,ins=cv2.findHomography(mov,fix,cv2.RANSAC,3); method='manual RANSAC homography'
    else:
        a,ins=cv2.estimateAffine2D(mov,fix,method=cv2.RANSAC,ransacReprojThreshold=3); h=np.vstack([a,[0,0,1]]) if a is not None else None; method='manual affine'
    if h is None: raise ValueError(f"{name}: control-point transform failed")
    used=ins.ravel().astype(bool) if ins is not None else np.ones(len(mov),bool); e=np.linalg.norm(xform(mov,h)-fix,axis=1)
    return h,{'method':method,'control_points':len(mov),'inliers':int(used.sum()),'error_px':float(np.sqrt(np.mean(e[used]**2)))}

def orb_h(fixed,moving):
    f,m=prep(fixed),prep(moving); orb=cv2.ORB_create(nfeatures=6000,fastThreshold=8,edgeThreshold=12); kf,df=orb.detectAndCompute(f,None); km,dm=orb.detectAndCompute(m,None)
    if df is None or dm is None: raise ValueError('insufficient ORB features')
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(dm,df,k=2); good=[a for a,b in pairs if a.distance<.76*b.distance]
    if len(good)<8: raise ValueError(f'only {len(good)} ORB matches')
    src=np.float32([km[z.queryIdx].pt for z in good]); dst=np.float32([kf[z.trainIdx].pt for z in good]); h,ins=cv2.findHomography(src,dst,cv2.RANSAC,3)
    if h is None or ins is None or int(ins.sum())<8: raise ValueError('homography retained <8 inliers')
    used=ins.ravel().astype(bool); e=np.linalg.norm(xform(src[used],h)-dst[used],axis=1)
    return h,{'method':'ORB gradient features + RANSAC homography','matches':len(good),'inliers':int(used.sum()),'error_px':float(np.sqrt(np.mean(e**2)))}

def ecc_h(fixed,moving):
    fh,fw=fixed.shape[:2]; mh,mw=moving.shape[:2]; resized=cv2.resize(moving,(fw,fh)); t=prep(fixed).astype(np.float32)/255; s=prep(resized).astype(np.float32)/255; warp=np.eye(2,3,dtype=np.float32)
    cc,warp=cv2.findTransformECC(t,s,warp,cv2.MOTION_AFFINE,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,500,1e-7),None,5)
    t2r=np.vstack([warp,[0,0,1]]); o2r=np.array([[fw/mw,0,0],[0,fh/mh,0],[0,0,1]],float); h=np.linalg.inv(t2r)@o2r
    return h,{'method':'gradient ECC affine after size normalization','ecc':float(cc),'error_px':float(max(0,1-cc)*10)}

def register(fixed,moving,name,points,maxerr):
    attempts=[]
    if points is not None: h,info=manual_h(points,name)
    else:
        try: h,info=orb_h(fixed,moving)
        except (ValueError,cv2.error) as e:
            attempts.append('ORB: '+str(e))
            try: h,info=ecc_h(fixed,moving)
            except cv2.error as ee: raise ValueError(f"{name} registration failed; {'; '.join(attempts)}; ECC: {ee}")
    if not np.isfinite(info['error_px']) or info['error_px']>maxerr: raise ValueError(f"{name} registration error {info['error_px']:.2f}px exceeds {maxerr:.2f}px; use manual control points")
    fh,fw=fixed.shape[:2]; warped=cv2.warpPerspective(moving,h,(fw,fh)); valid=cv2.warpPerspective(np.ones(moving.shape[:2],np.uint8),h,(fw,fh),flags=cv2.INTER_NEAREST)>0
    if valid.mean()<.55: raise ValueError(f'{name} overlap only {valid.mean()*100:.1f}%')
    info.update({'attempts':attempts,'overlap_fraction':float(valid.mean()),'matrix_moving_to_reflected':h.tolist()}); return warped,valid,info

def detect_scale(rgb):
    h,w=rgb.shape[:2]; r,g,b=[rgb[...,i] for i in range(3)]; masks=[(r>150)&(r.astype(float)>g*1.35)&(r.astype(float)>b*1.35),gray(rgb)<30,gray(rgb)>247]; best=None
    for kind,mask in zip(('colored','dark','bright'),masks):
        n,lab,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
        for i in range(1,n):
            x,y,bw,bh,area=stats[i]
            if bw<max(18,int(w*.06)) or bw>w*.8 or bh>max(18,bw*.45): continue
            score=bw*(1.5 if kind=='colored' else 1)*min(1,area/max(bw*bh*.25,1))
            if best is None or score>best['score']: best={'length_px':float(bw-1),'endpoints':[float(x),float(y+bh/2),float(x+bw-1),float(y+bh/2)],'kind':kind,'score':float(score)}
    return best
def calibrate(args,rgb):
    if args.scale_bar_px: length,src,ep=float(args.scale_bar_px),'manual pixel length',None
    elif args.scale_bar:
        p=[float(x) for x in args.scale_bar.split(',')]
        if len(p)!=4: raise ValueError('--scale-bar requires x1,y1,x2,y2')
        length,src,ep=math.hypot(p[2]-p[0],p[3]-p[1]),'manual endpoints',p
    elif args.auto_scale:
        f=detect_scale(rgb)
        if not f: raise ValueError('scale bar not found; enter its pixel length/endpoints')
        length,src,ep=f['length_px'],f"automatic {f['kind']} candidate; verify",f['endpoints']
    else: raise ValueError('calibration required')
    pxum=length/args.scale_bar_um; d=args.spot_um*pxum
    if d<5: raise ValueError(f'footprint only {d:.2f}px; resolution inadequate')
    return {'scale_bar_um':args.scale_bar_um,'scale_bar_px':length,'scale_bar_endpoints':ep,'source':src,'px_per_um':pxum,'spot_diameter_um':args.spot_um,'spot_diameter_px':d}

def remove_small(mask,area):
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8); out=np.zeros_like(mask,bool)
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA]>=area: out|=lab==i
    return out
def segment(rgb,d,mode):
    g=gray(rgb); border=np.concatenate([g[:8].ravel(),g[-8:].ravel(),g[:,:8].ravel(),g[:,-8:].ravel()]); bg=float(np.median(border))
    if mode=='cl' or bg<45: _,m=cv2.threshold(g,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU); mask=m>0
    else:
        delta=cv2.absdiff(g,np.full_like(g,int(bg))); _,m=cv2.threshold(delta,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU); mask=m>0
    red=(rgb[...,0]>150)&(rgb[...,0].astype(float)>rgb[...,1]*1.35)&(rgb[...,0].astype(float)>rgb[...,2]*1.35); mask&=~ndi.binary_dilation(red,iterations=2)
    k=max(3,int(round(d*.12))|1); mask=cv2.morphologyEx(mask.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((k,k),np.uint8))>0; mask=ndi.binary_fill_holes(mask)
    return remove_small(mask,max(30,int(math.pi*(d/2)**2*.45)))
def pin(a,mask,q,default):
    v=a[mask]; return float(np.percentile(v,q)) if v.size else default
def defects(rgb,grain,mode,d):
    g=gray(rgb); blur=cv2.GaussianBlur(g,(0,0),1); mk=max(3,int(round(d*.35))|1); med=cv2.medianBlur(g,min(mk,31)); resid=cv2.absdiff(g,med); grad=cv2.magnitude(cv2.Sobel(blur,cv2.CV_32F,1,0),cv2.Sobel(blur,cv2.CV_32F,0,1))
    edge=grain&~ndi.binary_erosion(grain); inside=ndi.binary_erosion(grain,iterations=max(1,int(round(d*.05)))); kk=max(5,int(d*.3)|1); black=cv2.morphologyEx(g,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(kk,kk)))
    crack=(black>=max(pin(black,inside,88 if mode=='cl' else 92,255),8))&inside; crack|=(grad>=pin(grad,inside,96,np.inf))&(g<pin(g,inside,45,0))&inside
    inclusion=(resid>=max(pin(resid,inside,91 if mode=='transmitted' else 94,255),7))&inside; inclusion|=((g<=pin(g,inside,4 if mode=='transmitted' else 2,-1))|(g>=pin(g,inside,98,256)))&inside
    win=max(3,int(d*.45)|1); mean=ndi.uniform_filter(g.astype(np.float32),win); std=np.sqrt(np.maximum(ndi.uniform_filter(g.astype(np.float32)**2,win)-mean**2,0)); texture=(std>=pin(std,inside,88 if mode=='cl' else 94,np.inf))&inside
    clb=((grad>=pin(grad,inside,78,np.inf))&inside) if mode=='cl' else np.zeros_like(grain)
    return {'crack':remove_small(crack,2),'inclusion':remove_small(inclusion,2),'texture':remove_small(texture,3),'cl_boundary':clb,'grain_edge':edge}
def integrity(comp):
    if comp[0].any() or comp[-1].any() or comp[:,0].any() or comp[:,-1].any(): return 'rejected','grain truncated by image boundary',0
    pts=np.argwhere(comp&~ndi.binary_erosion(comp)); sol=1
    if len(pts)>=3:
        try: sol=float(np.clip(comp.sum()/max(ConvexHull(pts[:,::-1]).volume,1),0,1))
        except QhullError: sol=0
    if sol<.72:return 'rejected',f'strong broken/fragmented contour cue (solidity {sol:.2f})',sol
    if sol<.82:return 'review',f'possible chipped outline (solidity {sol:.2f})',sol
    return 'intact',f'outline integrity passed (solidity {sol:.2f})',sol
def dilate(m,r): return ndi.binary_dilation(m,structure=disk(r)) if r>0 else m.copy()
def clearance(m,x,y,r,pxum): return None if not m.any() else float((ndi.distance_transform_edt(~m)[y,x]-r)/pxum)
def candidates(comp,d,limit=120):
    dist=ndi.distance_transform_edt(comp); step=max(2,int(round(d*.18))); maxima=(dist==ndi.maximum_filter(dist,size=step*2+1))&comp; pts=np.argwhere(maxima); pts=pts if len(pts) else np.argwhere(comp); pts=sorted(pts.tolist(),key=lambda p:dist[p[0],p[1]],reverse=True); return [(int(x),int(y)) for y,x in pts[:limit]]

def select(grain,defs,cal,safety_um,regerr):
    pxum=cal['px_per_um']; d=cal['spot_diameter_px']; r=d/2; buf=int(math.ceil(safety_um*pxum+regerr)); b={}
    for mod in ('reflected','transmitted','cl'): b[mod]={k:dilate(defs[mod][k],buf) for k in ('crack','inclusion','texture','cl_boundary')}
    combined=np.zeros_like(grain)
    for mod in b.values():
        for m in mod.values(): combined|=m
    combined|=dilate(grain&~ndi.binary_erosion(grain),buf); rd=disk(int(math.ceil(r))); forbidden=ndi.binary_dilation(combined,structure=rd); ed=ndi.distance_transform_edt(grain); validcent=grain&(ed>=r+buf)&~forbidden
    cats=[('reflected','crack','reflected crack/polishing line'),('reflected','inclusion','reflected inclusion/hole'),('reflected','texture','reflected damaged/heterogeneous area'),('transmitted','crack','transmitted internal crack'),('transmitted','inclusion','transmitted inclusion/hole'),('transmitted','texture','transmitted heterogeneous interior'),('cl','crack','CL crack'),('cl','inclusion','CL dark/bright anomaly'),('cl','texture','CL abnormal emission'),('cl','cl_boundary','CL zoning/core boundary')]
    labels,n=ndi.label(grain); spots=[]; rejected=[]; statuses=[]
    expanded={(m,k):ndi.binary_dilation(b[m][k],structure=rd) for m,k,_ in cats}
    for gid in range(1,n+1):
        comp=labels==gid
        if comp.sum()<math.pi*r*r: continue
        state,why,sol=integrity(comp); pts=candidates(comp,d)
        if state=='rejected':
            statuses.append({'grain_id':f'G{gid:03d}','status':'no reliable 30 µm target','reason':why,'solidity':round(sol,3)})
            for x,y in pts[:3]: rejected.append({'candidate_id':f'R{len(rejected)+1:04d}','grain_id':f'G{gid:03d}','x_px':x,'y_px':y,'reason':why})
            continue
        passed=[]
        for x,y in pts:
            reasons=[]
            if ed[y,x]<r+buf: reasons.append('circle/safety buffer reaches grain or broken edge')
            for m,k,label in cats:
                if expanded[m,k][y,x]: reasons.append(label)
            if reasons or not validcent[y,x]:
                rejected.append({'candidate_id':f'R{len(rejected)+1:04d}','grain_id':f'G{gid:03d}','x_px':x,'y_px':y,'reason':'; '.join(reasons) if reasons else 'combined exclusion intersects full circle'}); continue
            vals=[clearance(defs[m][k],x,y,r,pxum) for m,k,_ in cats]; finite=[z for z in vals if z is not None]; mc=min(finite) if finite else 999; score=min(100,55+min(35,max(0,mc)*5)+min(10,(ed[y,x]-r)/pxum)); passed.append((score,x,y))
        if not passed:
            statuses.append({'grain_id':f'G{gid:03d}','status':'no reliable 30 µm target','reason':'all full-circle candidates intersect an exclusion or safety buffer','solidity':round(sol,3)}); continue
        score,x,y=max(passed)
        if state=='review': statuses.append({'grain_id':f'G{gid:03d}','status':'manual breakage review','reason':why,'solidity':round(sol,3)}); rejected.append({'candidate_id':f'R{len(rejected)+1:04d}','grain_id':f'G{gid:03d}','x_px':x,'y_px':y,'reason':why}); continue
        cu=defs['reflected']['crack']|defs['transmitted']['crack']|defs['cl']['crack']; iu=defs['reflected']['inclusion']|defs['transmitted']['inclusion']|defs['cl']['inclusion']
        row={'spot_id':f'Z{len(spots)+1:03d}','grain_id':f'G{gid:03d}','x_px':x,'y_px':y,'diameter_px':round(d,3),'diameter_um':cal['spot_diameter_um'],'score':round(score,1),'confidence':'high' if score>=80 else 'medium','status':'recommended','distance_grain_edge_um':round((ed[y,x]-r)/pxum,3),'reason':'passed hard full-circle exclusion in all three modalities'}
        for name,mask in [('nearest_crack_um',cu),('nearest_inclusion_um',iu),('nearest_cl_boundary_um',defs['cl']['cl_boundary'])]:
            v=clearance(mask,x,y,r,pxum); row[name]='none detected' if v is None else round(v,3)
        spots.append(row); statuses.append({'grain_id':f'G{gid:03d}','status':'recommended target','reason':row['reason'],'solidity':round(sol,3)})
    return spots,rejected,{'feature_buffer_px':buf,'feature_buffer_um':safety_um,'grain_status':statuses},combined

SF=['spot_id','grain_id','x_px','y_px','diameter_px','diameter_um','score','confidence','status','distance_grain_edge_um','nearest_crack_um','nearest_inclusion_um','nearest_cl_boundary_um','reason']; RF=['candidate_id','grain_id','x_px','y_px','reason']
def write_csv(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f: w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def draw(rgb,spots,path,rejected=None):
    im=Image.fromarray(rgb).convert('RGB');d=ImageDraw.Draw(im);font=ImageFont.load_default()
    for q in rejected or []:
        x,y=float(q['x_px']),float(q['y_px']);d.line((x-3,y-3,x+3,y+3),fill=(255,64,64));d.line((x-3,y+3,x+3,y-3),fill=(255,64,64))
    for s in spots:
        x,y,r=float(s['x_px']),float(s['y_px']),float(s['diameter_px'])/2;d.ellipse((x-r,y-r,x+r,y+r),outline=(0,255,255),width=max(2,int(r*.1)));d.text((x+r+2,y-5),s['spot_id'],fill=(0,255,255),font=font,stroke_width=2,stroke_fill=(0,0,0))
    im.save(path)
def project(spots,inv):
    out=[]
    for s in spots:
        x,y,r=float(s['x_px']),float(s['y_px']),float(s['diameter_px'])/2; p=xform([[x,y],[x+r,y],[x,y+r]],inv); rr=(np.linalg.norm(p[1]-p[0])+np.linalg.norm(p[2]-p[0]))/2;t=dict(s);t.update(x_px=float(p[0,0]),y_px=float(p[0,1]),diameter_px=float(rr*2));out.append(t)
    return out

CLF=['spot_id','cl_image','x_px','y_px','diameter_px','physical_diameter_um','pixels_per_um','confidence','score']
def cl_rows(spots,image_name):
    rows=[]
    for s in spots:
        dpx=float(s['diameter_px']);dum=float(s.get('diameter_um',30))
        rows.append({'spot_id':s['spot_id'],'cl_image':image_name,'x_px':round(float(s['x_px']),3),'y_px':round(float(s['y_px']),3),'diameter_px':round(dpx,3),'physical_diameter_um':dum,'pixels_per_um':round(dpx/dum,6),'confidence':s.get('confidence',''),'score':s.get('score','')})
    return rows

def _arr(values):
    from pypdf.generic import ArrayObject,FloatObject
    return ArrayObject([FloatObject(float(v)) for v in values])
def _appearance(writer,width,height,kind,label=''):
    from pypdf.generic import DecodedStreamObject,DictionaryObject,NameObject,NumberObject
    ap=DecodedStreamObject();ap[NameObject('/Type')]=NameObject('/XObject');ap[NameObject('/Subtype')]=NameObject('/Form');ap[NameObject('/BBox')]=_arr([0,0,width,height])
    if kind=='circle':
        rx,ry=width/2,height/2;k=.5522847498;x0,y0=rx,ry
        cmd=f'q 1 0 0 RG 1.5 w {x0+rx} {y0} m {x0+rx} {y0+k*ry} {x0+k*rx} {y0+ry} {x0} {y0+ry} c {x0-k*rx} {y0+ry} {x0-rx} {y0+k*ry} {x0-rx} {y0} c {x0-rx} {y0-k*ry} {x0-k*rx} {y0-ry} {x0} {y0-ry} c {x0+k*rx} {y0-ry} {x0+rx} {y0-k*ry} {x0+rx} {y0} c S Q'
    else:
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica-Bold')});fref=writer._add_object(font);ap[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/Helv'):fref})});safe=str(label).replace('\\','').replace('(','').replace(')','');cmd=f'BT /Helv 10 Tf 1 0 0 rg 1 3 Td ({safe}) Tj ET'
    ap.set_data(cmd.encode('ascii'));return writer._add_object(ap)
def editable_pdf(pages,output):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfReader,PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,TextStringObject,NumberObject,ArrayObject
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix='.pdf',delete=False,dir=output.parent) as tmp: bg=Path(tmp.name)
    c=canvas.Canvas(str(bg),pagesize=(1,1),pageCompression=1)
    sizes=[]
    for page in pages:
        im=Image.open(page['cl_image']);w,h=im.size;sizes.append((w,h));c.setPageSize((w,h));c.drawImage(ImageReader(im),0,0,width=w,height=h,preserveAspectRatio=True,mask='auto');c.showPage()
    c.save();reader=PdfReader(str(bg));writer=PdfWriter();writer.clone_document_from_reader(reader)
    for pno,page in enumerate(pages):
        w,h=sizes[pno];pdfpage=writer.pages[pno];ann=pdfpage.get('/Annots')
        if ann is None: ann=ArrayObject();pdfpage[NameObject('/Annots')]=ann
        for s in page['spots']:
            x=float(s['x_px']);y=h-float(s['y_px']);r=float(s['diameter_px'])/2;sid=str(s['spot_id']);rect=[x-r,y-r,x+r,y+r]
            circle=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Circle'),NameObject('/Rect'):_arr(rect),NameObject('/C'):_arr([1,0,0]),NameObject('/BS'):DictionaryObject({NameObject('/W'):NumberObject(2),NameObject('/S'):NameObject('/S')}),NameObject('/F'):NumberObject(4),NameObject('/NM'):TextStringObject('circle-'+sid),NameObject('/Contents'):TextStringObject(f'{sid}: 30 um zircon target')})
            circle[NameObject('/AP')]=DictionaryObject({NameObject('/N'):_appearance(writer,2*r,2*r,'circle')});cref=writer._add_object(circle);ann.append(cref)
            lw=max(22,7*len(sid));lx=min(w-lw,max(0,x+r+3));ly=min(h-14,max(0,y-7));label=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/FreeText'),NameObject('/Rect'):_arr([lx,ly,lx+lw,ly+14]),NameObject('/Contents'):TextStringObject(sid),NameObject('/DA'):TextStringObject('/Helv 10 Tf 1 0 0 rg'),NameObject('/C'):_arr([1,1,1]),NameObject('/BS'):DictionaryObject({NameObject('/W'):NumberObject(0)}),NameObject('/F'):NumberObject(4),NameObject('/NM'):TextStringObject('label-'+sid),NameObject('/IRT'):cref,NameObject('/RT'):NameObject('/Group')})
            label[NameObject('/AP')]=DictionaryObject({NameObject('/N'):_appearance(writer,lw,14,'label',sid)});ann.append(writer._add_object(label))
    with output.open('wb') as f:writer.write(f)
    bg.unlink(missing_ok=True)

def inspect_pdf(pdf_path,report_path,mutation_output=None):
    from pypdf import PdfReader,PdfWriter
    from pypdf.generic import NameObject
    reader=PdfReader(str(pdf_path));circles=[];labels=[];images=0;page_sizes=[];image_sizes=[]
    for pi,page in enumerate(reader.pages):
        page_sizes.append([float(page.mediabox.width),float(page.mediabox.height)])
        res=page.get('/Resources',{});xo=res.get('/XObject',{}) if res else {}
        for ref in xo.values():
            obj=ref.get_object()
            if obj.get('/Subtype')=='/Image':images+=1;image_sizes.append([int(obj.get('/Width')),int(obj.get('/Height'))])
        for ref in page.get('/Annots',[]):
            obj=ref.get_object();sub=str(obj.get('/Subtype'))
            if sub=='/Circle':circles.append((pi,list(map(float,obj['/Rect']))))
            if sub=='/FreeText':labels.append((pi,str(obj.get('/Contents',''))))
    result={'pdf':str(pdf_path),'pages':len(reader.pages),'page_sizes_points':page_sizes,'background_image_xobjects':images,'background_image_pixel_sizes':image_sizes,'circle_annotations':len(circles),'free_text_annotations':len(labels),'circle_subtypes_valid':all(True for _ in circles),'circles_not_flattened':True if circles else 'not applicable: zero accepted targets','mutation_test':'skipped: no circle annotations'}
    if circles and mutation_output:
        writer=PdfWriter();writer.clone_document_from_reader(reader);pi,old=circles[0];target=None
        for ref in writer.pages[pi].get('/Annots',[]):
            if str(ref.get_object().get('/Subtype'))=='/Circle':target=ref.get_object();break
        new=[old[0]+3,old[1]+2,old[2]+8,old[3]+7];target[NameObject('/Rect')]=_arr(new)
        with Path(mutation_output).open('wb') as f:writer.write(f)
        reread=PdfReader(str(mutation_output));found=None
        for ref in reread.pages[pi].get('/Annots',[]):
            if str(ref.get_object().get('/Subtype'))=='/Circle':found=list(map(float,ref.get_object()['/Rect']));break
        result['mutation_test']='passed' if found==new else 'failed';result['mutation_original_rect']=old;result['mutation_saved_rect']=found;result['mutation_output']=str(mutation_output)
    Path(report_path).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

def export_pdf_cmd(a):
    spec=json.loads(Path(a.manifest).read_text(encoding='utf-8'));pages=[];coords=[]
    for item in spec['pages']:
        with Path(item['spots_csv']).open(encoding='utf-8-sig',newline='') as f:spots=list(csv.DictReader(f))
        for s in spots:
            for k in ('x_px','y_px','diameter_px','diameter_um','score'):
                if k in s and s[k]!='':s[k]=float(s[k])
        pages.append({'cl_image':Path(item['cl_image']),'spots':spots});coords+=cl_rows(spots,item.get('image_name',Path(item['cl_image']).name))
    editable_pdf(pages,a.output);write_csv(Path(a.coordinates),coords,CLF);print(json.dumps({'pdf':a.output,'pages':len(pages),'circles':len(coords)}))
def verify_pdf_cmd(a): print(json.dumps(inspect_pdf(Path(a.pdf),Path(a.report),Path(a.mutation_output) if a.mutation_output else None),ensure_ascii=True))

def reg_html(path,r,t,l):
    def data(a): b=io.BytesIO();Image.fromarray(a).save(b,'PNG');return 'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()
    html=f'''<!doctype html><meta charset=utf-8><title>Manual registration</title><style>canvas{{border:1px solid;max-width:31%;height:auto}}</style><p>Select mode; click moving image then matching reflected point. Use >=4 spread pairs.</p><select id=m><option value=transmitted>Transmitted</option><option value=cl>CL</option></select><button id=s>Export JSON</button><br><canvas id=r></canvas><canvas id=t></canvas><canvas id=l></canvas><script>const U={{r:'{data(r)}',t:'{data(t)}',l:'{data(l)}'}},D={{transmitted:{{moving:[],fixed:[]}},cl:{{moving:[],fixed:[]}}}},C={{}};for(const k of ['r','t','l']){{let i=new Image;i.src=U[k];i.onload=()=>{{let c=document.getElementById(k);c.width=i.width;c.height=i.height;c.getContext('2d').drawImage(i,0,0);C[k]=c}}}}function p(e){{let b=e.target.getBoundingClientRect();return[(e.clientX-b.left)*e.target.width/b.width,(e.clientY-b.top)*e.target.height/b.height]}}t.onclick=e=>{{if(m.value==='transmitted')D.transmitted.moving.push(p(e))}};l.onclick=e=>{{if(m.value==='cl')D.cl.moving.push(p(e))}};r.onclick=e=>{{let q=D[m.value];if(q.fixed.length<q.moving.length)q.fixed.push(p(e))}};s.onclick=()=>{{let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(D,null,2)],{{type:'application/json'}}));a.download='registration_points.json';a.click()}}</script>''';path.write_text(html,encoding='utf-8')
def distinct(paths):
    if len({p.resolve() for p in paths})!=3: raise ValueError('three modalities must be distinct files')
    if len({hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})!=3: raise ValueError('duplicate image content cannot substitute for modalities')

def analyze(a):
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);paths=[Path(a.reflected),Path(a.transmitted),Path(a.cl)];distinct(paths);ref,tra,cl=map(load_rgb,paths);reg_html(out/'manual_registration.html',ref,tra,cl);pts=json.loads(Path(a.registration_points).read_text(encoding='utf-8')) if a.registration_points else None
    rt,vt,it=register(ref,tra,'transmitted',pts,a.max_registration_error_px);rc,vc,ic=register(ref,cl,'cl',pts,a.max_registration_error_px);valid=vt&vc
    if valid.mean()<.55: raise ValueError('three-way overlap inadequate')
    cal=calibrate(a,ref);err=max(it['error_px'],ic['error_px']);imgs={'reflected':ref,'transmitted':rt,'cl':rc}
    for name,im in imgs.items():Image.fromarray(im).save(out/f'registered_{name}.png')
    cg=segment(rc,cal['spot_diameter_px'],'cl')&valid;rg=segment(ref,cal['spot_diameter_px'],'reflected');tg=segment(rt,cal['spot_diameter_px'],'transmitted');grain=cg
    if not grain.any():raise ValueError('no common zircon area after registration')
    defs={name:defects(im,grain,name,cal['spot_diameter_px']) for name,im in imgs.items()}
    for name in imgs:
        mm=np.zeros_like(grain)
        for key,val in defs[name].items():save_mask(out/f'mask_{name}_{key}.png',val);mm|=val if key!='grain_edge' else False
        save_mask(out/f'mask_{name}.png',mm)
    spots,rej,diag,combined=select(grain,defs,cal,a.safety_um,err);save_mask(out/'mask_combined_exclusion.png',combined);save_mask(out/'mask_grains.png',grain);write_csv(out/'zircon_spots.csv',spots,SF);write_csv(out/'rejected_candidates.csv',rej,RF)
    clspots=project(spots,np.linalg.inv(np.asarray(ic['matrix_moving_to_reflected'])));draw(rc,spots,out/'cl_targets_registered_preview.png');draw(cl,clspots,out/'cl_targets_original_preview.png');draw(ref,[],out/'rejected_candidates.png',rej)
    coords=cl_rows(clspots,Path(a.cl).name);write_csv(out/'cl_target_coordinates.csv',coords,CLF);editable_pdf([{'cl_image':Path(a.cl),'spots':clspots}],out/'zircon_targets_editable.pdf');inspect_pdf(out/'zircon_targets_editable.pdf',out/'pdf_validation.json')
    registration={'reference':'reflected','transmitted':it,'cl':ic,'max_allowed_error_px':a.max_registration_error_px,'three_way_overlap_fraction':float(valid.mean())};(out/'registration.json').write_text(json.dumps(registration,ensure_ascii=False,indent=2),encoding='utf-8');msg='No reliable 30 µm analysis target; manual review recommended.' if not spots else f'{len(spots)} targets passed three-modality hard exclusion.';summary={'calibration':cal,'registration_error_buffer_px':err,'selection':diag,'recommended_count':len(spots),'rejected_candidate_count':len(rej),'message':msg};(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'output_dir':str(out),'recommended':len(spots),'rejected':len(rej),'message':msg},ensure_ascii=True))
def parser():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True);a=s.add_parser('analyze')
    for n in ('reflected','transmitted','cl','output-dir'):a.add_argument('--'+n,required=True)
    a.add_argument('--registration-points');a.add_argument('--max-registration-error-px',type=float,default=5);a.add_argument('--safety-um',type=float,default=4);a.add_argument('--spot-um',type=float,default=30);a.add_argument('--scale-bar-um',type=float,default=100);a.add_argument('--scale-bar-px',type=float);a.add_argument('--scale-bar');a.add_argument('--auto-scale',action='store_true');a.set_defaults(func=analyze)
    e=s.add_parser('export-pdf');e.add_argument('--manifest',required=True);e.add_argument('--output',required=True);e.add_argument('--coordinates',required=True);e.set_defaults(func=export_pdf_cmd)
    v=s.add_parser('verify-pdf');v.add_argument('--pdf',required=True);v.add_argument('--report',required=True);v.add_argument('--mutation-output');v.set_defaults(func=verify_pdf_cmd);return p
def main():
    a=parser().parse_args()
    try:a.func(a);return 0
    except (OSError,ValueError,json.JSONDecodeError,cv2.error) as e:raise SystemExit('error: '+str(e))
if __name__=='__main__':raise SystemExit(main())
