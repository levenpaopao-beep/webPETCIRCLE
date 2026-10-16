"""只读检查发布商品的英文资料；不改源数据、上架状态或历史报价。"""
import json,os,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.languages import color_name_en,has_product_name

def check(db):
    connection=sqlite3.connect('file:'+str(Path(db).resolve())+'?mode=ro',uri=True);connection.row_factory=sqlite3.Row
    issues=[];products=list(connection.execute('SELECT code,name_en FROM products WHERE published=1 AND present=1'))
    for product in products:
        if not has_product_name(product['code'],product['name_en']):issues.append({'code':product['code'],'problem':'英文品名待核对'})
        for variant in connection.execute('SELECT sku,color,size FROM variants WHERE code=?',(product['code'],)):
            if color_name_en(variant['color'],variant['sku']) is None:issues.append({'code':product['code'],'sku':variant['sku'],'problem':'英文颜色或图案待核对'})
    connection.close();return products,issues
if __name__=='__main__':
    db=Path(os.environ.get('PETCIRCLE_SITE_STATE',str(ROOT/'.local')))/'website.sqlite'
    if not db.exists():print('缺少产品副本，不能完成商品语言发布检查。');raise SystemExit(1)
    products,issues=check(db)
    print(json.dumps({'publishedProducts':len(products),'issues':issues},ensure_ascii=False,indent=2));raise SystemExit(1 if issues else 0)
