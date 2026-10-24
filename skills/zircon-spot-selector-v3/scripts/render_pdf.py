"""Render every page for human inspection; exit success is not geological review."""
import argparse,json,subprocess
from pathlib import Path
from pypdf import PdfReader
from PIL import Image

def render(pdf,destination,poppler='pdftoppm',dpi=96):
    destination=Path(destination)
    if destination.exists():raise FileExistsError('preserve prior render evidence; choose a new directory')
    destination.mkdir(parents=True)
    result=subprocess.run([str(poppler),'-png','-r',str(dpi),str(pdf),str(destination/'page')],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    images=sorted(destination.glob('page-*.png'))
    if len(images)!=len(PdfReader(pdf).pages):raise ValueError('rendered page count mismatch')
    records=[]
    for image in images:
        with Image.open(image) as im:records.append({'file':image.name,'size':list(im.size)})
    audit={'pages':records,'renderer_messages':result.stderr,'visual_review':'pending human inspection','geological_accuracy':'not assessed'}
    (destination/'render.json').write_text(json.dumps(audit,indent=2),'utf-8');return audit

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pdf',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--poppler',default='pdftoppm');ap.add_argument('--dpi',type=int,default=96);a=ap.parse_args();render(a.pdf,a.output_dir,a.poppler,a.dpi)
