import unittest
from server.languages import CONFIG,normalize_language,document_messages,localized
class LanguageTests(unittest.TestCase):
 def test_presets_and_public_gate(self):
  self.assertEqual([r['code'] for r in CONFIG['languages']],['zh','en','ru','es'])
  for value in ['ru','es','unknown',None,{}]:self.assertEqual(normalize_language(value),'en')
  self.assertEqual(normalize_language('zh'),'zh')
 def test_document_fallback(self):
  self.assertEqual(document_messages('ru'),document_messages('en'))
  self.assertEqual(document_messages('es'),document_messages('en'))
  self.assertEqual(document_messages('zh')['title'],'客户报价')
  self.assertEqual(localized({'en':'Product'},'ru'),'Product')

class TranslationQualityTests(unittest.TestCase):
 def test_color_phrases_and_unknown(self):
  from server.languages import color_name_en
  cases={'米白':'Off-white','深蓝':'Dark blue','咖啡色':'Brown','绿白条':'Green & White stripes','红绿条':'Red & Green stripes','红白条':'Red & White stripes','黑白条':'Black & White stripes','藏青':'Navy','军绿':'Army green'}
  for source,expected in cases.items():self.assertEqual(color_name_en(source),expected)
  self.assertIsNone(color_name_en('未经核对的图案'))
  self.assertEqual(color_name_en('毛刺','20250619-06'),'Purple bat')
  self.assertEqual(color_name_en('鬼南瓜','20250619-14'),'Skull & pumpkin')
 def test_product_names_and_document_terms(self):
  from server.languages import product_name_en,has_product_name
  self.assertIn('sweater',product_name_en('10100057-1','Christmas Pet Outfit'))
  self.assertIn('neckwear',product_name_en('20250619-16','Halloween Pet Outfit'))
  self.assertFalse(has_product_name('unknown','零售A01'))
  self.assertTrue(has_product_name('3303177031','零售A01'))
  self.assertEqual(document_messages('zh')['pieces'],'件')
  self.assertEqual(document_messages('en')['xlsxHeads'][-1],'Carton dimensions (reference)')
 def test_customer_business_errors_have_english(self):
  import ast,re,json
  from pathlib import Path
  root=Path(__file__).resolve().parents[1]
  messages=json.loads((root/'shared/business-messages.json').read_text())
  tree=ast.parse((root/'server/app.py').read_text())
  missing=[]
  for node in ast.walk(tree):
   if isinstance(node,ast.Raise) and isinstance(node.exc,ast.Call) and node.exc.args and isinstance(node.exc.args[0],ast.Constant):
    text=node.exc.args[0].value
    if isinstance(text,str) and re.search('[\u3400-\u9fff]',text) and text not in messages:missing.append(text)
  self.assertEqual(missing,[])
