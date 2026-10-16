"""官网分类以 ERP 原分类为底稿；一次导入后归属由管理员维护。"""
import hashlib,json

ENGLISH={
'12元':'CNY 12','15元':'CNY 15','5元':'CNY 5','8元':'CNY 8',
'2026年秋冬':'Autumn / Winter 2026','2026春夏':'Spring / Summer 2026',
'万圣节衣服':'Halloween Clothing','万圣节饰品':'Halloween Accessories',
'三角巾&围嘴':'Bandanas & Bibs','光板':'Blank Clothing',
'加加定制款':'Jiajia Custom Styles','加加宠物':'Jiajia Pet Products','加加烫画片':'Jiajia Heat Transfers',
'变身装':'Costumes','四脚&背带裤':'Four-Legged Outfits & Overalls',
'圆领衫&卫衣&带帽衫':'Crewnecks, Sweatshirts & Hoodies',
'圣诞衣服':'Christmas Clothing','圣诞饰品':'Christmas Accessories',
'外套马甲':'Coats & Vests','外购玩具':'Sourced Toys','头纱':'Veils','头饰&发夹':'Headwear & Hair Clips',
'婚纱礼服':'Wedding & Formal Wear','宝宝家居':'Baobao Homewear','客人定制款':'Customer Custom Styles',
'布料':'Fabrics','常规辅料':'Standard Trims','帽子':'Hats','库存玩具':'Toys in Stock',
'情人节款':'Valentine’s Day Styles','情人节衣服':'Valentine’s Day Clothing','情人节饰品':'Valentine’s Day Accessories',
'成衣刺绣':'Embroidered Clothing','打底衫&睡衣&居家服':'Base Layers, Pajamas & Loungewear',
'新年款':'New Year Styles','春夏薄款':'Lightweight Spring / Summer Clothing','春夏裙子':'Spring / Summer Dresses',
'杂':'Miscellaneous','杂款混发':'Mixed Styles','棉衣厚款':'Padded & Heavyweight Clothing',
'毛绒玩具':'Plush Toys','毛衣':'Knitwear','浴巾':'Bath Towels','清仓产品':'Clearance',
'烫画片':'Heat Transfers','牛仔':'Denim','牵引绳':'Leashes','特殊辅料':'Specialty Trims',
'甜心':'Sweetheart','生理裤':'Dog Diapers & Sanitary Pants','眼镜&墨镜':'Glasses & Sunglasses',
'秋冬裙子':'Autumn / Winter Dresses','绣花':'Embroidery','赠品':'Complimentary Items',
'门廊鹅':'Porch Goose Products','雨衣':'Raincoats','项圈&项链':'Collars & Necklaces','饰品':'Accessories'
}

def import_erp_categories(c,source):
    """显式一次性替换；重复执行不会重置用户删减、改名或产品归属。"""
    if c.execute("SELECT 1 FROM metadata WHERE key='erp_categories_initialized'").fetchone():
        raise ValueError('ERP分类底稿已经导入，不可重复覆盖人工调整')
    names=sorted({str(x).strip() for x in source['masterCategories']+source['quotationCategories'] if str(x).strip()})
    if not names or any(name not in ENGLISH for name in names):raise ValueError('ERP分类英文名称待核对')
    conflicts={code:v for code,v in source['productCategories'].items() if len(v)!=1}
    if conflicts:raise ValueError('ERP产品分类存在冲突，导入未执行')
    # 旧分类仅停用，产品归属原值另随迁移备份保存。
    c.execute('UPDATE categories SET active=0')
    lookup={}
    for i,name in enumerate(names):
        key='erp-'+hashlib.sha256(name.encode()).hexdigest()[:20];lookup[name]=key
        c.execute('INSERT INTO categories(id,zh,en,position,active) VALUES(?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET zh=excluded.zh,en=excluded.en,position=excluded.position,active=1',(key,name,ENGLISH[name],i))
        c.execute('INSERT INTO erp_category_map VALUES(?,?)',(name,key))
    changed=0
    for row in c.execute('SELECT code,source_category FROM products').fetchall():
        cats=source['productCategories'].get(row['code'])
        name=cats[0] if cats else row['source_category']
        c.execute('UPDATE products SET category=? WHERE code=?',(lookup.get(name,''),row['code']));changed+=1
    c.execute("INSERT INTO metadata VALUES('erp_categories_initialized',?)",(json.dumps({'categories':len(names),'quotationTime':source.get('quotationTime'),'masterTime':source.get('masterTime')},ensure_ascii=False),))
    return {'categories':len(names),'products':changed}

def category_ids(c,code):
    return [r[0] for r in c.execute('SELECT pc.category_id FROM product_categories pc JOIN categories t ON t.id=pc.category_id WHERE pc.code=? AND t.active=1 ORDER BY t.position,t.id',(code,))]

def set_product_categories(c,code,ids,mode='replace'):
    if not isinstance(ids,list) or len(ids)>300 or any(not isinstance(x,str) for x in ids):raise ValueError('请选择有效分类')
    ids=list(dict.fromkeys(ids))
    if mode not in ['replace','add','remove']:raise ValueError('请选择归类操作')
    if any(not c.execute('SELECT 1 FROM categories WHERE id=? AND active=1',(x,)).fetchone() for x in ids):raise ValueError('请选择有效分类')
    if mode=='replace':c.execute('DELETE FROM product_categories WHERE code=?',(code,))
    for key in ids:
        if mode=='remove':c.execute('DELETE FROM product_categories WHERE code=? AND category_id=?',(code,key))
        else:c.execute('INSERT OR IGNORE INTO product_categories VALUES(?,?)',(code,key))
    remaining=category_ids(c,code)
    c.execute('UPDATE products SET category=? WHERE code=?',(remaining[0] if remaining else '',code))

def list_categories(c):
    result=[]
    for row in c.execute('SELECT id,zh,en,position,parent_id AS parentId FROM categories WHERE active=1 ORDER BY position,id'):
        d=dict(row);d['sourceNames']=[r[0] for r in c.execute('SELECT source_name FROM erp_category_map WHERE category_id=?',(row['id'],))]
        members='SELECT pc.code FROM product_categories pc JOIN categories t ON t.id=pc.category_id WHERE t.active=1 AND (t.id=? OR t.parent_id=?)'
        d['publishedCount']=c.execute('SELECT count(*) FROM products WHERE present=1 AND published=1 AND code IN ('+members+')',(row['id'],row['id'])).fetchone()[0]
        d['productCount']=c.execute('SELECT count(*) FROM products WHERE present=1 AND code IN ('+members+')',(row['id'],row['id'])).fetchone()[0]
        result.append(d)
    return [item for parent in result if not parent['parentId'] for item in [parent]+[child for child in result if child['parentId']==parent['id']]]

def save_categories(c,rows,replace=False):
    import re
    from server.languages import valid_english_name
    if not isinstance(rows,list) or len(rows)>300 or (not rows and not replace):raise ValueError('请填写分类')
    checked=[];seen=set()
    for i,r in enumerate(rows):
        key=str(r.get('id',''));zh=str(r.get('zh','')).strip();en=str(r.get('en','')).strip();parent=str(r.get('parentId') or '')
        if not re.fullmatch('[a-z0-9-]{1,40}',key) or not zh or len(zh)>60 or len(en)>100 or not valid_english_name(en):raise ValueError('分类名称不完整')
        if key in seen or (zh,parent) in {(x[1],x[4]) for x in checked}:raise ValueError('分类名称或编号重复')
        seen.add(key);checked.append((key,zh,en,i,parent))
    parents={r[0]:r[4] for r in checked}
    if not replace:
        for r in c.execute('SELECT id,parent_id FROM categories WHERE active=1'):parents.setdefault(r[0],r[1])
    if any(parent and (parent==key or parent not in parents or parents[parent]) for key,parent in parents.items()):raise ValueError('子分类只能归属一个主分类，请先调整所属子分类')
    if replace:
        for row in c.execute('SELECT id FROM categories WHERE active=1').fetchall():
            if row['id'] not in seen:
                codes=[r[0] for r in c.execute('SELECT code FROM product_categories WHERE category_id=?',(row['id'],))]
                c.execute('UPDATE categories SET active=0 WHERE id=?',(row['id'],))
                c.execute('DELETE FROM product_categories WHERE category_id=?',(row['id'],))
                for code in codes:
                    ids=category_ids(c,code);c.execute('UPDATE products SET category=? WHERE code=?',(ids[0] if ids else '',code))
    for row in checked:c.execute('INSERT INTO categories(id,zh,en,position,parent_id,active) VALUES(?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET zh=excluded.zh,en=excluded.en,position=excluded.position,parent_id=excluded.parent_id,active=1',row)
