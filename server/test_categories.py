"""分类导入、人工维护与同步保留；全部使用隔离数据库。"""
import json,tempfile,unittest
from pathlib import Path
from server import app
from server.categories import import_erp_categories,list_categories,save_categories

class CategoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=app.STATE,app.DB,app.SOURCE
  app.STATE=Path(self.tmp.name);app.DB=app.STATE/'site.sqlite';app.SOURCE=app.STATE/'empty-source';app.init()
  with app.connect() as c:
   c.execute("INSERT INTO products(code,name_zh,name_en,source_category,category) VALUES('A','名称像裙子的毛衣','Sweater','毛衣','dresses')")
  self.source={'masterCategories':['毛衣','春夏裙子','特殊辅料'],'quotationCategories':['毛衣','加加定制款'],'productCategories':{'A':['毛衣']},'masterTime':'2026-10-16','quotationTime':'2026-10-16'}
 def tearDown(self):app.STATE,app.DB,app.SOURCE=self.old;self.tmp.cleanup()
 def seed(self):
  with app.connect() as c:return import_erp_categories(c,self.source)
 def test_import_exact_source_and_one_time_guard(self):
  self.assertEqual(self.seed()['categories'],4)
  with app.connect() as c:
   cats=list_categories(c);self.assertEqual({x['zh'] for x in cats},{'毛衣','春夏裙子','特殊辅料','加加定制款'})
   knit=next(x for x in cats if x['zh']=='毛衣');self.assertEqual(c.execute("SELECT category FROM products WHERE code='A'").fetchone()[0],knit['id'])
   self.assertEqual(knit['productCount'],1)
   with self.assertRaises(ValueError):import_erp_categories(c,self.source)
  app.init()
  with app.connect() as c:self.assertEqual(len(list_categories(c)),4)
 def test_remove_rename_and_restart_preserve_manual_choices(self):
  self.seed()
  with app.connect() as c:
   cats=list_categories(c);knit=next(x for x in cats if x['zh']=='毛衣');knit['zh']='我选的针织';knit['en']='Selected Knitwear'
   save_categories(c,cats,True)
   self.assertEqual(next(x for x in list_categories(c) if x['id']==knit['id'])['zh'],'我选的针织')
   save_categories(c,[x for x in cats if x['id']!=knit['id']],True)
   self.assertEqual(c.execute("SELECT category FROM products WHERE code='A'").fetchone()[0],'')
   self.assertEqual(c.execute('SELECT active FROM categories WHERE id=?',(knit['id'],)).fetchone()[0],0)
  app.init()
  with app.connect() as c:self.assertNotIn(knit['id'],[x['id'] for x in list_categories(c)])
 def test_sync_maps_only_new_styles_and_preserves_manual_categories(self):
  self.seed()
  snapshot=app.STATE/'snapshot.json';config=app.STATE/'config.json';config.write_text(json.dumps({'cn':{},'fob':{}}))
  data={'status':'success','completeness':'complete','rows':[{'code':code,'sku':code+'-S','category':'毛衣','name_cn':'名字像裙子','name_en':'Pet sweater','spec':'红/S','price':10,'available':1} for code in ['A','N']]};snapshot.write_text(json.dumps(data))
  with app.connect() as c:
   save_categories(c,[{'id':'manual','zh':'人工精选','en':'Selected Styles'}])
   c.execute("UPDATE products SET category='manual' WHERE code='A'")
   knit=next(x for x in list_categories(c) if x['zh']=='毛衣')['id']
  app.sync(snapshot,config)
  with app.connect() as c:
   self.assertEqual(c.execute("SELECT category FROM products WHERE code='A'").fetchone()[0],'manual')
   self.assertEqual(c.execute("SELECT category FROM products WHERE code='N'").fetchone()[0],knit)
   save_categories(c,[x for x in list_categories(c) if x['id']!=knit],True)
  data['rows'].append({'code':'NEW','sku':'NEW-S','category':'毛衣','name_cn':'新品','spec':'S','price':10,'available':1});snapshot.write_text(json.dumps(data));app.sync(snapshot,config)
  with app.connect() as c:self.assertEqual(c.execute("SELECT category FROM products WHERE code='NEW'").fetchone()[0],'')
 def test_conflict_and_invalid_save_make_no_partial_changes(self):
  self.source['productCategories']['A']=['毛衣','春夏裙子']
  with app.connect() as c:
   before=list_categories(c)
   with self.assertRaises(ValueError):import_erp_categories(c,self.source)
   self.assertEqual(list_categories(c),before)
   with self.assertRaises(ValueError):save_categories(c,[{'id':'x','zh':'重复','en':'One'},{'id':'y','zh':'重复','en':'Two'}],True)
   self.assertEqual(list_categories(c),before)

 def test_published_count_changes_without_removing_admin_category(self):
  self.seed()
  with app.connect() as c:
   def knit():return next(x for x in list_categories(c) if x['zh']=='毛衣')
   self.assertEqual(knit()['productCount'],1);self.assertEqual(knit()['publishedCount'],0)
   c.execute("UPDATE products SET published=1 WHERE code='A'");self.assertEqual(knit()['publishedCount'],1)
   c.execute("UPDATE products SET published=0 WHERE code='A'");self.assertEqual(knit()['publishedCount'],0)
   self.assertEqual(len(list_categories(c)),4)
   c.execute("UPDATE products SET published=1,present=0 WHERE code='A'");self.assertEqual(knit()['publishedCount'],0)

if __name__=='__main__':unittest.main()

class MultiCategoryTests(unittest.TestCase):
 setUp=CategoryTests.setUp
 tearDown=CategoryTests.tearDown
 def test_multi_membership_parent_rollup_and_removal(self):
  from server.categories import set_product_categories,category_ids
  with app.connect() as c:
   save_categories(c,[{'id':'parent','zh':'服装','en':'Clothing'},{'id':'child','zh':'冬装','en':'Winter Clothing','parentId':'parent'},{'id':'other','zh':'精选','en':'Selected'}],True)
   set_product_categories(c,'A',['parent','child','other'])
   c.execute("UPDATE products SET published=1 WHERE code='A'")
   cats={x['id']:x for x in list_categories(c)}
   self.assertEqual(cats['parent']['productCount'],1)
   self.assertEqual(cats['parent']['publishedCount'],1)
   self.assertEqual(cats['child']['parentId'],'parent')
   set_product_categories(c,'A',['child'],'remove')
   self.assertEqual(set(category_ids(c,'A')),{'parent','other'})
   save_categories(c,[x for x in list_categories(c) if x['id'] not in ['parent','child']],True)
   self.assertEqual(category_ids(c,'A'),['other'])
 def test_reject_cycles_and_three_levels_without_change(self):
  with app.connect() as c:
   before=list_categories(c)
   for rows in [
    [{'id':'a','zh':'甲','en':'A','parentId':'b'},{'id':'b','zh':'乙','en':'B','parentId':'a'}],
    [{'id':'a','zh':'甲','en':'A'},{'id':'b','zh':'乙','en':'B','parentId':'a'},{'id':'c','zh':'丙','en':'C','parentId':'b'}]]:
    with self.assertRaises(ValueError):save_categories(c,rows,True)
    self.assertEqual(list_categories(c),before)
 def test_restart_migrates_once_and_preserves_empty_and_multiple(self):
  from server.categories import set_product_categories,category_ids
  with app.connect() as c:set_product_categories(c,'A',['knitwear','dresses'])
  app.init()
  with app.connect() as c:
   self.assertEqual(set(category_ids(c,'A')),{'knitwear','dresses'})
   set_product_categories(c,'A',[])
  app.init()
  with app.connect() as c:self.assertEqual(category_ids(c,'A'),[])
 def test_sync_retains_multiple_manual_memberships(self):
  from server.categories import set_product_categories,category_ids
  config=app.STATE/'config.json';config.write_text(json.dumps({'cn':{},'fob':{}}))
  snapshot=app.STATE/'snapshot.json';snapshot.write_text(json.dumps({'status':'success','completeness':'complete','rows':[{'code':'A','sku':'A-S','category':'毛衣','name_cn':'产品','spec':'红/S','price':10,'available':1}]}))
  with app.connect() as c:set_product_categories(c,'A',['knitwear','dresses'])
  app.sync(snapshot,config)
  with app.connect() as c:self.assertEqual(set(category_ids(c,'A')),{'knitwear','dresses'})
