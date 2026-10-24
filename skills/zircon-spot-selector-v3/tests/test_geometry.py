"""Meaningful geometry/state/mapping regressions; synthetic fixtures are not geological truth."""
import copy,json,tempfile,unittest,sys
from pathlib import Path
from PIL import Image
from pypdf import PdfWriter,PdfReader
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pdf_engine as z
class Checks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd());self.d=Path(self.tmp.name);assert self.d.resolve().is_relative_to(Path.cwd().resolve());Image.new('RGB',(120,100),'gray').save(self.d/'raw.png');w=PdfWriter();w.add_blank_page(width=600,height=500)
  with (self.d/'source.pdf').open('wb') as f:w.write(f)
  self.p={'source_pdf':'source.pdf','objective':'detrital_provenance','sampling_strategy':'synthetic fixture only','beam_diameter_um':10,'numbering_start':1,'target_count':1,'count_basis':'candidates','include_image_uncertain':True,'one_per_grain':True,'required_modalities':['CL'],'fields':[{'id':'f','page':1,'cl_image':'raw.png','image_size_px':[120,100],'pdf_rect':[0,0,600,500],'scale':{'endpoints_px':[[0,0],[100,0]],'value_um':50,'verified':True,'isotropic_verified':True},'uncertainty_um':{'registration':None,'temporary_margin':1}}], 'spots':[{'key':'p','grain_key':'g','field':'f','xy_px':[60,50],'include_in_main':True,'coverage':'full','image_judgment':'uncertain','positioning':'pending','observation':'synthetic point, no geological claim','pending_issues':'synthetic E unknown','domain_review':'synthetic uniform region','identity_basis':'synthetic same image','whole_footprint_reviewed':True,'panels':{'CL':{'path':'raw.png'}},'interior_polygon_px':[[10,10],[110,10],[110,90],[10,90]]}]}
 def tearDown(self):self.tmp.cleanup()
 def check(self):return z.validate(self.p,self.d)
 def test_circle_edge_hits_line_despite_clean_center(self):
  self.p['spots'][0]['obstacles']=[{'kind':'polyline','points_px':[[69,40],[69,60]],'certainty':'confirmed'}]
  with self.assertRaisesRegex(ValueError,'intersects confirmed'):self.check()
 def test_unknown_E_not_zero_and_uncertain_not_accepted(self):
  _,main,result=self.check();self.assertEqual(main[0]['_unknown_terms'],['registration']);self.assertEqual(result['accepted_count'],0);self.p['spots'][0]['manual_acceptance']=True
  with self.assertRaisesRegex(ValueError,'acceptance claims'):self.check()
 def test_duplicate_and_same_grain(self):
  self.p['spots'].append(copy.deepcopy(self.p['spots'][0]))
  with self.assertRaisesRegex(ValueError,'duplicate stable'):self.check()
  self.p['spots'][1]['key']='q'
  with self.assertRaisesRegex(ValueError,'same grain'):self.check()
  self.p['spots'][1]['grain_key']='h'
  with self.assertRaisesRegex(ValueError,'overlapping'):self.check()
 def test_new_scale_replaces_old_pixels(self):
  self.assertEqual(self.check()[1][0]['_diameter_px'],[20,20]);self.p['beam_diameter_um']=15;self.assertEqual(self.check()[1][0]['_diameter_px'],[30,30])
 def test_anisotropic_scale(self):
  self.p['fields'][0]['scale_y']={'endpoints_px':[[0,0],[0,100]],'value_um':100,'verified':True};self.assertEqual(self.check()[1][0]['_diameter_px'],[20,10])
 def test_missing_or_unverified_scale(self):
  self.p['fields'][0]['scale']['isotropic_verified']=False
  with self.assertRaisesRegex(ValueError,'isotropic'):self.check()
 def test_partial_not_counted_as_regular(self):
  self.p['spots'][0]['coverage']='partial'
  with self.assertRaisesRegex(ValueError,'alternate'):self.check()
 def test_shortage_kept_honest(self):
  self.p['target_count']=3;self.assertEqual(self.check()[2]['shortfall'],2);self.p['require_target_count']=True
  with self.assertRaisesRegex(ValueError,'differs'):self.check()
 def test_known_budget_acceptance_requires_evidence(self):
  s=self.p['spots'][0];s.update(image_judgment='suitable',positioning='sufficient',manual_acceptance=True,acceptance_basis='synthetic assertion',positioning_evidence='synthetic local controls');self.p['fields'][0]['uncertainty_um']={'registration':0.5,'extra':1};self.assertEqual(self.check()[2]['accepted_count'],1)
 def test_boundary_whole_circle(self):
  self.p['spots'][0]['xy_px']=[14,50]
  with self.assertRaisesRegex(ValueError,'outside reviewed grain'):self.check()
 def test_export_scaled_geometry_and_independent_edit_reopen(self):
  pp=self.d/'plan.json';pp.write_text(json.dumps(self.p),encoding='utf-8');out=self.d/'out.pdf';z.export(pp,out,self.d/'points.csv',self.d/'counts.json');result=z.verify(pp,out,self.d/'verify.json',self.d/'edits');self.assertTrue(result['circle_and_text_edit_save_reopen']);a=next(a.get_object() for a in PdfReader(out).pages[0]['/Annots'] if a.get_object()['/Subtype']=='/Circle');self.assertAlmostEqual(float(a['/Rect'][2]-a['/Rect'][0]),100)
 def test_explicit_positive_counter_start(self):
  self.p['numbering_start']=11;self.assertEqual(self.check()[1][0]['_number'],11)
if __name__=='__main__':unittest.main()
