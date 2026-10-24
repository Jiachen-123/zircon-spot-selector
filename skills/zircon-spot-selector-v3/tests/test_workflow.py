"""Synthetic engineering regressions; no geological labels or private sample images."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import workflow as z
from PIL import Image,ImageDraw
from pypdf import PdfReader,PdfWriter

def fixture(folder,sample='synthetic-A'):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGB',(240,180),'#20252a');d=ImageDraw.Draw(image);d.ellipse((20,20,220,160),fill='#aaaaaa');d.line((70,55,160,55),fill='#eeeeee',width=2);image.save(folder/'raw.png')
    w=PdfWriter();w.add_blank_page(width=480,height=360)
    with (folder/'source.pdf').open('wb') as stream:w.write(stream)
    registry={'sample_id':sample,'features':[],'note':'Synthetic geometry only, not evidence of defect-free zircon.'};z.atomic_json(folder/'defects.json',registry)
    p={'sample_id':sample,'source_pdf':'source.pdf','objective':'synthetic_geometry','objective_status':'specified','sampling_strategy':'synthetic','beam_diameter_um':12,'numbering_start':1,'target_count':2,'minimum_count':2,'count_basis':'candidates','include_image_uncertain':True,'one_per_grain':True,'required_modalities':['CL'],'defect_registry':{'path':'defects.json','sha256':z.file_hash(folder/'defects.json')},'fields':[{'id':'f','page':1,'cl_image':'raw.png','image_size_px':[240,180],'pdf_rect':[0,0,480,360],'scale':{'endpoints_px':[[10,170],[210,170]],'value_um':100,'verified':True,'isotropic_verified':True},'uncertainty_um':{'registration':None,'engineering_margin':None}}],'spots':[]}
    for i,x in enumerate([90,150],1):
        p['spots'].append({'key':f'p{i}','sample_id':sample,'grain_key':f'g{i}','field':'f','xy_px':[x,100],'include_in_main':True,'coverage':'full','image_judgment':'suitable','positioning':'pending','observation':'Synthetic footprint inside drawn shape; not a geological assessment.','pending_issues':'No real imaging or laboratory positioning evidence.','domain_review':'Synthetic continuous region, no inferred age.','identity_basis':'Synthetic raw fixture.','whole_footprint_reviewed':True,'panels':{'CL':{'path':'raw.png','native_box_px':[0,0,240,180]}},'interior_polygon_px':[[20,30],[220,30],[220,150],[20,150]],'history':[],'aliases':{'origin':'new'}})
    return seal(p,folder)

def seal(plan,folder):
    for s in plan['spots']:z.record_review(plan,s['key'],folder,'synthetic-test','Engineering fixture inspection only.')
    return plan

class Checks(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd());self.d=Path(self.tmp.name);self.p=fixture(self.d)
    def tearDown(self):self.tmp.cleanup()
    def check(self,p=None):return z.prepare(p or self.p,self.d)
    def test_independent_page_scales(self):
        self.assertEqual(self.check()[1][0]['_diameter_px'],[24,24]);f=copy.deepcopy(self.p['fields'][0]);f['id']='g';f['scale']['value_um']=200;self.p['fields'].append(f);self.p['spots'][1]['field']='g';seal(self.p,self.d);self.assertEqual(self.check()[1][1]['_diameter_px'],[12,12])
    def test_crop_scale_rotate_coordinate_and_ellipse(self):
        # Crop origin (10,20), scale 2, clockwise 90 around height 160.
        m=[[0,-2,360],[2,0,-20],[0,0,1]]
        self.assertEqual(z.transform(m,[30,50]),[260,40]);self.assertEqual(z.ellipse_rect(m,[30,50],[10,20]),[240,30,280,50])
        with self.assertRaisesRegex(ValueError,'shear'):z.ellipse_rect([[1,1,0],[0,1,0],[0,0,1]],[30,50],[10,10])
        self.p['fields'][0]['pdf_transform']=[[0,2,0],[-2,0,480],[0,0,1]];self.p['fields'][0]['pdf_rect']=[0,0,360,480];seal(self.p,self.d)
        f=self.check()[0]['fields'][0];rect=z.engine.mapped_rect(f,[90,100],[24,24]);self.assertEqual(rect,[176,276,224,324])
    def test_samples_number_separately_and_export(self):
        for sample in ['synthetic-A','synthetic-B']:
            folder=self.d/sample;p=fixture(folder,sample);z.atomic_json(folder/'plan.json',p);result=z.export_bundle(folder/'plan.json',folder/'version1');self.assertEqual(result['candidate_count'],2)
            rd=PdfReader(folder/'version1/spots.pdf');labels=[str(a.get_object()['/Contents']) for a in rd.pages[0]['/Annots'] if a.get_object()['/Subtype']=='/FreeText'];self.assertEqual(labels,['1','2'])
    def test_cross_sample_rejected(self):
        self.p['spots'][0]['sample_id']='other';seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'cross-sample'):self.check()
    def test_repeated_panels_count_once_and_cross_view_duplicates(self):
        self.p['spots'][0]['panels']['TL']=copy.deepcopy(self.p['spots'][0]['panels']['CL']);seal(self.p,self.d);self.assertEqual(self.check()[2]['candidate_count'],2)
        f=self.p['fields'][0];f['physical_frame']='mount';f['native_to_frame_um']=[[.5,0,0],[0,.5,0],[0,0,1]];g=copy.deepcopy(f);g['id']='repeat';self.p['fields'].append(g);t=self.p['spots'][1];t['field']='repeat';t['xy_px']=self.p['spots'][0]['xy_px'][:];seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'across views'):self.check()
    def test_independent_states_not_accepted(self):
        s=self.p['spots'][0];s['image_judgment']='uncertain';s['resolution_attempts']=[{'action':'shift assessed','result':'unresolved synthetic feature'}];seal(self.p,self.d);a=self.check()[2];self.assertEqual((a['image_suitable'],a['image_uncertain'],a['positioning_pending'],a['accepted_count']),(1,1,2,0))
    def test_move_requires_rereview_and_synchronizes_bundle(self):
        old=copy.deepcopy(self.p['spots'][0]);s=self.p['spots'][0];s['xy_px']=[100,100];s['history']=[{'from':old['xy_px'],'to':s['xy_px'],'action':'move','reason':'synthetic shift'}];s['previous_panel']=copy.deepcopy(s['panels']['CL']);s['previous_spot']={k:old[k] for k in ['field','grain_key','xy_px']}
        with self.assertRaisesRegex(ValueError,'stale'):self.check()
        seal(self.p,self.d);z.atomic_json(self.d/'plan.json',self.p);result=z.export_bundle(self.d/'plan.json',self.d/'bundle');self.assertEqual(result['candidate_count'],2)
        state=json.loads((self.d/'bundle/state.json').read_text('utf-8'));self.assertEqual(state['spots'][0]['xy_px'],[100,100]);self.assertIn('100',(self.d/'bundle/coordinates.csv').read_text('utf-8-sig'));rd=PdfReader(self.d/'bundle/spots.pdf');circle=rd.pages[0]['/Annots'][0].get_object();self.assertAlmostEqual((float(circle['/Rect'][0])+float(circle['/Rect'][2]))/2,200)
        atlas=PdfReader(self.d/'bundle/review-atlas.pdf');self.assertEqual(len(atlas.pages),2);self.assertEqual(json.loads(atlas.pages[0]['/Annots'][0].get_object()['/Contents'])['key'],'p1')
    def test_atomic_resume_and_changed_evidence(self):
        path=self.d/'checkpoint.json';z.checkpoint(path,self.p,self.d,'next page');z.checkpoint(path,self.p,self.d,'next grain');saved=z.resume(path);self.assertEqual(len(saved['history']),2);self.assertEqual(saved['next_step'],'next grain');(self.d/'raw.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed since'):z.resume(path)
    def test_shortage_without_new_default(self):
        self.p['target_count']=5;self.p['minimum_count']=3;self.assertEqual((self.check()[2]['shortfall'],self.check()[2]['minimum_shortfall']),(3,1));self.p['target_count']=None;self.assertIsNone(self.check()[2]['shortfall'])
    def test_known_defect_cannot_be_laundered_by_state_or_duplicate(self):
        registry={'sample_id':self.p['sample_id'],'features':[{'field':'f','kind':'polyline','points_px':[[100,85],[100,115]],'certainty':'confirmed','description':'synthetic line','source_evidence':'synthetic drawing'}]};z.atomic_json(self.d/'defects.json',registry);self.p['defect_registry']['sha256']=z.file_hash(self.d/'defects.json');seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'intersects confirmed'):self.check()
        self.p['spots'][0]['image_judgment']='suitable';seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'intersects confirmed'):self.check()
        self.p['spots'].append(copy.deepcopy(self.p['spots'][0]));seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.check()
    def test_unknown_objective_explicit_not_inferred(self):
        self.p['objective']=None;self.p['objective_status']='pending';seal(self.p,self.d);self.assertTrue(self.check()[2]['objective_pending']);self.p['objective_status']='specified'
        with self.assertRaisesRegex(ValueError,'unknown objective'):self.check()
    def test_partial_coverage_separate(self):
        self.p['spots'][0]['coverage']='partial';seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'alternate'):self.check()
    def test_editable_objects_appearance_and_original_pages(self):
        z.atomic_json(self.d/'plan.json',self.p);z.export_bundle(self.d/'plan.json',self.d/'bundle');report=json.loads((self.d/'bundle/pdf-verification.json').read_text('utf-8'));self.assertTrue(report['circle_and_text_edit_save_reopen']);self.assertTrue(report['source_contents_and_images_preserved']);edited=PdfReader(self.d/'bundle/edit-tests/FreeText_edit_reopen.pdf');a=edited.pages[0]['/Annots'][1].get_object();self.assertEqual(a['/Contents'],'EDIT-TEST');self.assertIn(b'(EDIT-TEST)',a['/AP']['/N'].get_object().get_data())
    def test_evidence_or_scale_change_invalidates_review(self):
        self.p['fields'][0]['scale']['value_um']=99
        with self.assertRaisesRegex(ValueError,'stale'):self.check()
    def test_uncertain_requires_resolution_attempt(self):
        self.p['spots'][0]['image_judgment']='uncertain';seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'investigation'):self.check()
    def test_rotated_native_mapping_export(self):
        w=PdfWriter();w.add_blank_page(width=360,height=480)
        with (self.d/'source.pdf').open('wb') as stream:w.write(stream)
        f=self.p['fields'][0];f['pdf_transform']=[[0,2,0],[-2,0,480],[0,0,1]];f['pdf_rect']=[0,0,360,480];seal(self.p,self.d);z.atomic_json(self.d/'plan.json',self.p);z.export_bundle(self.d/'plan.json',self.d/'rotated');rd=PdfReader(self.d/'rotated/spots.pdf');rect=list(rd.pages[0]['/Annots'][0].get_object()['/Rect']);self.assertEqual(rect,[176,276,224,324])
    def test_wrong_native_size_and_unknown_positioning_budget(self):
        self.p['fields'][0]['image_size_px']=[100,100]
        with self.assertRaisesRegex(ValueError,'native image size'):self.check()
        self.p['fields'][0]['image_size_px']=[240,180];s=self.p['spots'][0];s['positioning']='sufficient';s['positioning_evidence']='synthetic controls';seal(self.p,self.d)
        with self.assertRaisesRegex(ValueError,'unknown positioning'):self.check()

if __name__=='__main__':unittest.main()
