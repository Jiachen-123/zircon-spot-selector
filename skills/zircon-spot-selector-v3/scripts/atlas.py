"""Evidence atlas: nine cells, unmarked originals, current and previous footprint.
Optical panels never receive an unverified precise beam projection.
"""
import json,textwrap
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from pypdf import PdfReader,PdfWriter
from pypdf.generic import NameObject,ArrayObject
import pdf_engine as engine

def panel_draw(c,panel,base,x,y,w=270,h=210):
    if not panel:
        c.setFont('STSong-Light',12);c.drawString(x+8,y+h/2,'No available image / 未提供');return None
    path=engine.resolve(base,panel['path'])
    with Image.open(path) as im:iw,ih=im.size
    ratio=min(w/iw,h/ih);dw,dh=iw*ratio,ih*ratio;left=x+(w-dw)/2;bottom=y+(h-dh)/2
    c.drawImage(str(path),left,bottom,dw,dh)
    return left,bottom,dw,dh,iw,ih

def footprint(panel,placement,field,spot,plan):
    if not placement:return None
    # CL native crop supports translation only. Other transformed crops require a
    # separately verified mapping and are deliberately not guessed by this helper.
    box=panel.get('native_box_px')
    if not box:return None
    left,bottom,dw,dh,iw,ih=placement
    if abs(box[2]-box[0]-iw)>1e-6 or abs(box[3]-box[1]-ih)>1e-6:raise ValueError('atlas crop size differs from recorded native box')
    px,py=engine.scales(field);cx=(spot['xy_px'][0]-box[0])*dw/iw+left;cy=bottom+dh-(spot['xy_px'][1]-box[1])*dh/ih;rx=plan['beam_diameter_um']*px/2*dw/iw;ry=plan['beam_diameter_um']*py/2*dh/ih
    if cx-rx<left or cy-ry<bottom or cx+rx>left+dw or cy+ry>bottom+dh:raise ValueError('atlas crop clips actual footprint; recrop')
    return [cx-rx,cy-ry,cx+rx,cy+ry]

def build_atlas(plan,base,output):
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));main=[s for s in plan['spots'] if s.get('include_in_main')];fields={f['id']:f for f in plan['fields']};tmp=Path(output).with_suffix('.background.pdf');c=canvas.Canvas(str(tmp),pagesize=(900,1040));annotations=[]
    for index,s in enumerate(main):
        number=plan['numbering_start']+index;field=fields[s['field']];c.setFillColorRGB(.96,.97,.98);c.rect(0,0,900,1040,fill=1,stroke=0);c.setFillColorRGB(.05,.08,.1);c.setFont('STSong-Light',16);c.drawString(20,1012,f"{plan['sample_id']} | {number} | {s['grain_key']} | source page {field['page']}")
        xs=[20,315,610];ys=[750,500,250];current=[]
        for row in [0,1]:
            for j,mode in enumerate(['CL','TL','RL']):
                p=s.get('panels',{}).get(mode) if row==0 else s.get('defect_panels',{}).get(mode)
                c.setFont('STSong-Light',12);c.drawString(xs[j],ys[row]+220,mode+(' raw / 无标注' if row==0 else ' defects / 缺陷证据'))
                panel_draw(c,p,base,xs[j],ys[row])
        old=s.get('previous_panel');oldspot=s.get('previous_spot');titles=['Previous / 新增则无旧位','Current / 本轮','Before vs current / 对照']
        for j in range(3):c.setFont('STSong-Light',12);c.drawString(xs[j],ys[2]+220,titles[j])
        po=panel_draw(c,old,base,xs[0],ys[2]);pc=s.get('panels',{}).get('CL');p1=panel_draw(c,pc,base,xs[1],ys[2]);p2=panel_draw(c,pc,base,xs[2],ys[2])
        for placement in [p1,p2]:
            rect=footprint(pc,placement,field,s,plan)
            if rect is None:raise ValueError('CL native crop box required for atlas footprint')
            current.append(rect)
        if old and oldspot:
            oldfield=fields[oldspot['field']];rect=footprint(old,po,oldfield,oldspot,plan)
            if rect:
                c.setStrokeColorRGB(.1,.4,.9);c.setLineWidth(1);c.ellipse(*rect,stroke=1,fill=0)
            if oldspot['field']==s['field'] and oldspot.get('grain_key')==s['grain_key']:
                try:rect=footprint(pc,p2,field,oldspot,plan)
                except ValueError:rect=None
                if rect:c.setStrokeColorRGB(.1,.4,.9);c.ellipse(*rect,stroke=1,fill=0)
        c.setFillColorRGB(.05,.08,.1);c.setFont('STSong-Light',11)
        lines=[f"image={s['image_judgment']} | positioning={s['positioning']} | accepted={bool(s.get('manual_acceptance'))} | beam={plan['beam_diameter_um']} um",s['observation'],s['pending_issues'],'Optical panels: contextual correspondence only unless independent precise mapping is recorded.']
        y=220
        for text in lines:
            for line in textwrap.wrap(str(text),90):c.drawString(20,y,line);y-=15
        if y<15:raise ValueError('atlas notes overflow; shorten notes and link detailed record')
        annotations.append((index,number,s,current));c.showPage()
    c.save();w=PdfWriter();w.clone_document_from_reader(PdfReader(tmp))
    for index,number,s,rects in annotations:
        pg=w.pages[index];pg[NameObject('/Annots')]=ArrayObject()
        for j,rect in enumerate(rects):
            engine.annotate(w,pg,rect,number,s['key'],{'image':s['image_judgment'],'positioning':s['positioning'],'accepted':bool(s.get('manual_acceptance'))},1.1,12,[315+j*295,ys[2]+185,355+j*295,ys[2]+205])
    with Path(output).open('wb') as stream:w.write(stream)
    tmp.unlink()
