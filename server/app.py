"""PETCIRCLE 独立官网服务。工作台只读同步，公开接口仅返回业务展示字段。"""
from __future__ import annotations
import argparse, base64, hashlib, hmac, io, json, math, mimetypes, os, re, secrets, shutil, sqlite3, subprocess, tempfile, threading, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import urllib.request
from zoneinfo import ZoneInfo
from server.categories import list_categories, save_categories, category_ids, set_product_categories
from server.languages import normalize_language, document_messages, color_name_en, product_name_en, valid_english_name, has_product_name

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('PETCIRCLE_SITE_STATE', str(ROOT / '.local')))
SOURCE = Path(os.environ.get('PETCIRCLE_WORKBENCH', '/Users/levenwong/Documents/全托日常运营工作台/dailywork'))
DB = STATE / 'website.sqlite'
SIZES = ['XXS','XS','S','M','L','XL','XXL','2XL','3XL','4XL','5XL','6XL','7XL','8XL','均码']
BLOCKED = {'WJ-20207301','WJ-20200801-1','WJ-20200801-2','WJ-20200801-3','YF00001','A05F14-J15-XS'}
PRICE_OVERRIDES={'3303177362':14.0,'3303177361':14.0}
EXCLUDED = {'12元','8元','5元','外购玩具','客人定制款','布料','杂','甜心','清仓产品','牵引绳','项圈&项链','辅料','赠品','杂款混发','加加成品','头饰&发夹','烫画片','绣花','眼镜&墨镜','加加定做款','加加定制款','加加宠物','客户定制款'}
# 明确的成品分类；未知分类暂不进入官网候选，不改工作台源资料。
FINISHED_CATEGORIES = {'2026年秋冬','婚纱礼服','成衣刺绣','圣诞衣服','牛仔','圆领衫&卫衣&带帽衫','外套马甲','变身装','毛衣','光板','情人节衣服','打底衫&睡衣&居家服','万圣节衣服','四脚&背带裤','2026春夏','棉衣厚款','帽子','春夏裙子','生理裤','春夏薄款','新年款','三角巾&围嘴','秋冬裙子','宝宝家居','雨衣','圣诞饰品','浴巾','万圣节饰品','门廊鹅','毛绒玩具','头纱','15元','情人节饰品','情人节款','饰品','库存玩具'}
def is_finished_category(category):
    parts={part.strip() for part in str(category or '').split('/') if part.strip()}
    return bool(parts & FINISHED_CATEGORIES) and not bool(parts & EXCLUDED) and not any(re.search(r'辅料|布料|面料|耗材|包装|烫画片',part) for part in parts)

CATEGORIES = [('knitwear','毛衣','Knitwear'),('sweatshirts','卫衣','Sweatshirts'),('coats','外套','Coats & Vests'),('dresses','裙子','Dresses'),('loungewear','居家服','Loungewear'),('costumes','变身装','Costumes'),('accessories','配饰','Accessories')]
EXPORT_NODE = Path('/Users/levenwong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
MESSAGE_ATTEMPTS = defaultdict(list)
ATTEMPTS = defaultdict(list)
ATTEMPT_LOCK = threading.Lock()
IMAGE_LOCK=threading.Lock()
SYNC_STATE={'running':False,'error':'','result':None}
SYNC_LOCK=threading.Lock()
TRUSTED_IMAGES={'img.alicdn.com','cbu01.alicdn.com','cbu01.alicdn.com.cn','erpx-prod.oss-cn-zhangjiakou.aliyuncs.com'}

def now(): return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def connect():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c
def money(value): return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
def integer(v, lo=0, hi=1000000):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or int(v)!=v or not lo<=v<=hi: raise ValueError('请输入有效的整数数量')
    return int(v)
def number(v):
    try:
        n=float(str(v).replace(',','')); return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None
def public_user(row):
    return {k:row[k] for k in ['id','email','contact','company','country','phone','currency','role']}
def hash_password(password, salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def password_matches(password, stored):
    return hmac.compare_digest(hash_password(password,stored.split(':')[0]),stored)

def init():
    STATE.mkdir(parents=True,exist_ok=True); os.chmod(STATE,0o700)
    (STATE/'images').mkdir(exist_ok=True); (STATE/'quote-images').mkdir(exist_ok=True)
    with connect() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,contact TEXT NOT NULL,company TEXT NOT NULL,country TEXT NOT NULL,phone TEXT NOT NULL DEFAULT '',currency TEXT NOT NULL DEFAULT 'USD',role TEXT NOT NULL DEFAULT 'customer',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS categories(id TEXT PRIMARY KEY,zh TEXT NOT NULL,en TEXT NOT NULL,position INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS products(code TEXT PRIMARY KEY,name_zh TEXT NOT NULL,name_en TEXT NOT NULL,source_category TEXT NOT NULL,category TEXT NOT NULL,published INTEGER NOT NULL DEFAULT 0,featured INTEGER NOT NULL DEFAULT 0,position INTEGER NOT NULL DEFAULT 100,photo TEXT NOT NULL DEFAULT '',present INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS erp_category_map(source_name TEXT PRIMARY KEY,category_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_image_candidates(code TEXT NOT NULL REFERENCES products(code),filename TEXT NOT NULL,PRIMARY KEY(code,filename));
        CREATE TABLE IF NOT EXISTS product_content(code TEXT PRIMARY KEY REFERENCES products(code),images TEXT NOT NULL DEFAULT '[]',description_zh TEXT NOT NULL DEFAULT '',description_en TEXT NOT NULL DEFAULT '',guide_zh TEXT NOT NULL DEFAULT '',guide_en TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS variants(sku TEXT PRIMARY KEY,code TEXT REFERENCES products(code),color TEXT,size TEXT,price REAL,available REAL,weight REAL,carton_qty REAL,carton_size TEXT);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT NOT NULL,wechat TEXT NOT NULL,company TEXT NOT NULL,message TEXT NOT NULL,language TEXT NOT NULL,source TEXT NOT NULL,unread INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,request_key TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),number TEXT UNIQUE,snapshot TEXT NOT NULL,total REAL NOT NULL,quantity INTEGER NOT NULL,currency TEXT NOT NULL,first_inquiry INTEGER NOT NULL,unread INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,request_key TEXT NOT NULL,UNIQUE(user_id,request_key));
        ''')
        if 'image_url' not in [r[1] for r in c.execute('PRAGMA table_info(products)')]:c.execute("ALTER TABLE products ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
        if 'active' not in [r[1] for r in c.execute('PRAGMA table_info(categories)')]:c.execute('ALTER TABLE categories ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        if 'parent_id' not in [r[1] for r in c.execute('PRAGMA table_info(categories)')]:c.execute("ALTER TABLE categories ADD COLUMN parent_id TEXT NOT NULL DEFAULT ''")
        c.execute('CREATE TABLE IF NOT EXISTS product_categories(code TEXT NOT NULL REFERENCES products(code),category_id TEXT NOT NULL REFERENCES categories(id),PRIMARY KEY(code,category_id))')
        c.executescript("""
        CREATE TRIGGER IF NOT EXISTS product_category_insert AFTER INSERT ON products
        WHEN NEW.category!='' BEGIN
          INSERT OR IGNORE INTO product_categories SELECT NEW.code,id FROM categories WHERE id=NEW.category AND active=1;
        END;
        CREATE TRIGGER IF NOT EXISTS product_category_legacy_update AFTER UPDATE OF category ON products
        WHEN NEW.category!=OLD.category AND (NEW.category='' OR NOT EXISTS(SELECT 1 FROM product_categories WHERE code=NEW.code AND category_id=NEW.category)) BEGIN
          DELETE FROM product_categories WHERE code=NEW.code;
          INSERT OR IGNORE INTO product_categories SELECT NEW.code,id FROM categories WHERE id=NEW.category AND active=1;
        END;
        """)
        if not c.execute("SELECT 1 FROM metadata WHERE key='multi_categories_initialized'").fetchone():
            c.execute("INSERT OR IGNORE INTO product_categories SELECT p.code,p.category FROM products p JOIN categories t ON t.id=p.category WHERE t.active=1")
            c.execute("INSERT INTO metadata VALUES('multi_categories_initialized','1')")
        if not c.execute("SELECT 1 FROM metadata WHERE key='erp_categories_initialized'").fetchone():
            for i,(k,zh,en) in enumerate(CATEGORIES):c.execute('INSERT OR IGNORE INTO categories(id,zh,en,position) VALUES(?,?,?,?)',(k,zh,en,i))
        if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            password=secrets.token_urlsafe(18)
            c.execute('INSERT INTO users(email,password,contact,company,country,currency,role,created_at) VALUES(?,?,?,?,?,?,?,?)',('admin@petcircle.local',hash_password(password),'管理员','PETCIRCLE','China','USD','admin',now()))
            p=STATE/'管理员登录.txt';p.write_text('仅用于本机测试，不得公开发布。\n邮箱：admin@petcircle.local\n密码：'+password+'\n');os.chmod(p,0o600)

def sync(snapshot_path=None, settings_path=None):
    """保存网站独立副本；保留上架状态、排序、分类、客户及历史。"""
    p=Path(snapshot_path or STATE/'source-snapshot.json'); sp=Path(settings_path or STATE/'source-settings.json')
    data=json.loads(p.read_text()); settings=json.loads(sp.read_text())
    if data.get('status')!='success' or data.get('completeness')!='complete':raise ValueError('工作台产品资料尚未完整，同步未执行')
    rows=data.get('rows')
    if not isinstance(rows,list) or not rows:raise ValueError('产品资料为空，同步未执行')
    grouped=defaultdict(list)
    for r in rows:
        if r.get('code') and r.get('sku') and r['sku'] not in BLOCKED:grouped[str(r['code'])].append(r)
    with connect() as c:
        c.execute('UPDATE products SET present=0')
        c.execute('DELETE FROM variants')
        for code,rs in grouped.items():
            first=rs[0];cat=str(first.get('category') or '');name=str(first.get('name_cn') or code)
            if not is_finished_category(cat):continue
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',code):continue
            candidates=list((SOURCE/'基础数据库/客户报价/图片缓存').glob(code+'.*'))
            photo=''
            saved=STATE/'images'/f'{code}.jpg'
            if saved.is_file():photo=saved.name
            for candidate in candidates:
                try:
                    from PIL import Image,ImageOps
                    with Image.open(candidate) as img:
                        img=ImageOps.exif_transpose(img).convert('RGB');img.thumbnail((1200,1200));target=STATE/'images'/f'{code}.jpg';img.save(target,'JPEG',quality=90);photo=target.name;break
                except (OSError,ValueError):continue
            is_new=not c.execute('SELECT 1 FROM products WHERE code=?',(code,)).fetchone()
            c.execute('INSERT INTO products(code,name_zh,name_en,source_category,category,photo,present) VALUES(?,?,?,?,?,?,1) ON CONFLICT(code) DO UPDATE SET name_zh=excluded.name_zh,name_en=excluded.name_en,source_category=excluded.source_category,photo=CASE WHEN EXISTS(SELECT 1 FROM product_content WHERE code=excluded.code) THEN products.photo ELSE excluded.photo END,present=1',(code,name,str(first.get('name_en') or ''),cat,next((r[0] for r in c.execute('SELECT m.category_id FROM erp_category_map m JOIN categories t ON t.id=m.category_id WHERE m.source_name=? AND t.active=1',(cat,))),''),photo))
            if is_new:
                assigned=c.execute('SELECT category FROM products WHERE code=?',(code,)).fetchone()[0]
                if assigned:set_product_categories(c,code,[assigned])
            url=str(first.get('image_url') or '')
            if url.startswith('//'):url='https:'+url
            c.execute('UPDATE products SET image_url=? WHERE code=?',(url,code))
            for r in rs:
                spec=str(r.get('spec') or '');sku=str(r['sku']);parts=[x.strip() for x in re.split(r'[/|]',spec) if x.strip()]
                suffix=sku[len(code)+1:].upper() if sku.startswith(code+'-') else '';last=parts[-1].upper() if parts else ''
                raw=str(r.get('size') or '');size=raw.upper() if raw else suffix if suffix in SIZES else last if last in SIZES else '均码'
                color=str(r.get('color') or '') or '/'.join(parts[:-1] if last==size else parts)
                c.execute('INSERT OR REPLACE INTO variants VALUES(?,?,?,?,?,?,?,?,?)',(sku,code,color,size,number(r.get('price')) or PRICE_OVERRIDES.get(code),number(r.get('available')),number(r.get('unit_weight_g')),number(r.get('carton_qty')),str(r.get('carton_size') or '')))
        meta={'source_time':str(data.get('synced_at') or ''),'imported_at':now(),'settings':json.dumps({'cn':settings['cn'],'fob':settings['fob']},ensure_ascii=False)}
        for k,v in meta.items():c.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',(k,v))
        return {'products':c.execute('SELECT count(*) FROM products WHERE present=1').fetchone()[0],'sourceTime':meta['source_time']}

def ensure_image(p,c):
    if p['photo'] and (STATE/'images'/p['photo']).is_file():return p['photo']
    url=p['image_url']
    def safe(u):
        parsed=urlparse(u)
        if parsed.scheme!='https' or parsed.hostname not in TRUSTED_IMAGES or parsed.port not in [None,443]:raise ValueError('产品图片待完善，请稍后重试')
    safe(url)
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            safe(newurl);return super().redirect_request(req,fp,code,msg,headers,newurl)
    with IMAGE_LOCK:
        target=STATE/'images'/f'{p["code"]}.jpg'
        if not target.is_file():
            request=urllib.request.Request(url,headers={'User-Agent':'PETCIRCLE-Website/1.0'})
            with urllib.request.build_opener(Redirect()).open(request,timeout=15) as response:raw=response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError('产品图片待完善，请稍后重试')
            from PIL import Image,ImageOps
            with Image.open(io.BytesIO(raw)) as im:
                if im.width*im.height>40000000:raise ValueError('产品图片待完善，请稍后重试')
                im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1200,1200));im.save(target,'JPEG',quality=90)
        c.execute('UPDATE products SET photo=? WHERE code=?',(target.name,p['code']))
        return target.name

def sync_formal():
    with SYNC_LOCK:
        SYNC_STATE.update(running=True,error='',result=None)
    try:
        with tempfile.TemporaryDirectory(dir=STATE) as tmp:
            for remote,local in [('erp_quotation_snapshot.json','snapshot.json'),('settings.json','settings.json')]:
                subprocess.run(['scp','-q','petcircle-formal:/opt/petcircle/current/基础数据库/客户报价/'+remote,str(Path(tmp)/local)],check=True,capture_output=True,timeout=90)
            result=sync(Path(tmp)/'snapshot.json',Path(tmp)/'settings.json')
            for name,target in [('snapshot.json','source-snapshot.json'),('settings.json','source-settings.json')]:shutil.copy2(Path(tmp)/name,STATE/target)
        with SYNC_LOCK:SYNC_STATE.update(result=result)
    except Exception:
        with SYNC_LOCK:SYNC_STATE.update(error='产品资料暂未更新，请稍后重试或联系管理员')
    finally:
        with SYNC_LOCK:SYNC_STATE.update(running=False)

def settings(c):
    row=c.execute("SELECT value FROM metadata WHERE key='settings'").fetchone()
    if not row:raise ValueError('产品资料尚未同步，请联系工作人员')
    return json.loads(row[0])
def unit_price(price, currency, quantity, s):
    if currency=='CNY': return money(price)
    f=s['fob'];rate=f['tier3Rate'] if quantity>=f['tier3Qty'] else f['tier2Rate'] if quantity>=f['tier2Qty'] else 1
    return money(Decimal(str(price))*Decimal(str(f['markupRate']))/Decimal(str(f['exchangeRate']))*Decimal(str(rate)))
def translate_color(s,sku=''):
    value=color_name_en(s,sku)
    return value if value is not None else ('Variant '+sku if sku else 'Translation pending')
def product_content(p,c):
    r=c.execute('SELECT * FROM product_content WHERE code=?',(p['code'],)).fetchone()
    d=dict(r) if r else dict(code=p['code'],images='[]',description_zh='',description_en='',guide_zh='',guide_en='')
    d['images']=json.loads(d['images'])
    if not r and p['photo']:d['images']=[p['photo']]
    return d

def erp_image_choices(code):
    """仅从已有 ERP 同步文件取图，不触发 ERP 更新或写入。"""
    urls=[]
    source=SOURCE/'erp数据源/erp产品基础信息表_接口同步_最新.xlsx'
    if source.is_file():
        import openpyxl
        book=openpyxl.load_workbook(source,read_only=True,data_only=True)
        try:
            for sheet in book:
                rows=sheet.iter_rows(values_only=True);headers=next(rows,())
                for values in rows:
                    row=dict(zip(headers,values))
                    if str(row.get('货品编码') or '')!=code:continue
                    for key in ['规格图片地址','货品图片地址','图片地址']:
                        u=str(row.get(key) or '')
                        if u.startswith('https://') and urlparse(u).hostname in TRUSTED_IMAGES and u not in urls:urls.append(u)
        finally:book.close()
    return urls[:100]

def pull_erp_images(c,code):
    if not c.execute('SELECT 1 FROM products WHERE code=? AND present=1',(code,)).fetchone():raise ValueError('产品不存在')
    choices=erp_image_choices(code)
    from concurrent.futures import ThreadPoolExecutor
    def fetch(url):
        try:return image_bytes(url,choices)
        except Exception:return None
    names=[];failed=0
    with ThreadPoolExecutor(max_workers=5) as pool:
        for raw in pool.map(fetch,choices):
            if raw is None:failed+=1;continue
            name='product-'+hashlib.sha256(raw).hexdigest()+'.jpg'
            if name in names:continue
            names.append(name);path=STATE/'images'/name
            if not path.exists():
                try:
                    with path.open('xb') as f:f.write(raw)
                except FileExistsError:pass
            c.execute('INSERT OR IGNORE INTO product_image_candidates VALUES(?,?)',(code,name))
    return {'erpImages':[r[0] for r in c.execute('SELECT filename FROM product_image_candidates WHERE code=?',(code,))],'failed':failed}

def image_bytes(value,choices):
    if value.startswith('data:'):
        match=re.fullmatch(r'data:image/(?:jpeg|png|webp);base64,([A-Za-z0-9+/=]+)',value)
        if not match:raise ValueError('图片格式不支持')
        try:raw=base64.b64decode(match[1],validate=True)
        except ValueError:raise ValueError('图片内容无效')
    else:
        if value not in choices:raise ValueError('请选择该款的 ERP 图片')
        def safe(url):
            parsed=urlparse(url)
            if parsed.scheme!='https' or parsed.hostname not in TRUSTED_IMAGES or parsed.port not in (None,443):raise ValueError('图片来源不支持')
        safe(value)
        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):
                safe(newurl);return super().redirect_request(req,fp,code,msg,headers,newurl)
        with urllib.request.build_opener(Redirect()).open(value,timeout=15) as response:raw=response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('每张图片不能超过 8MB')
    from PIL import Image,ImageOps
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>40000000:raise ValueError('图片尺寸过大')
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1800,1800));out=io.BytesIO();im.save(out,'JPEG',quality=92);return out.getvalue()
    except (OSError,Image.DecompressionBombError):raise ValueError('图片内容无效')

def save_product_content(c,payload):
    p=c.execute('SELECT * FROM products WHERE code=? AND present=1',(str(payload.get('code','')),)).fetchone()
    if not p:raise ValueError('产品不存在')
    old=product_content(p,c);images=payload.get('images',[])
    if not isinstance(images,list) or not 1<=len(images)<=5:raise ValueError('每款保留 1 至 5 张图片')
    choices=erp_image_choices(p['code']) if any(isinstance(x,str) and x.startswith('https:') for x in images) else []
    pending={}
    def resolve(value,allowed):
        if not isinstance(value,str):raise ValueError('图片内容无效')
        if value in allowed:return value
        raw=image_bytes(value,choices);name='product-'+hashlib.sha256(raw).hexdigest()+'.jpg';pending[name]=raw;return name
    available=old['images']+[r[0] for r in c.execute('SELECT filename FROM product_image_candidates WHERE code=?',(p['code'],))]
    names=list(dict.fromkeys(resolve(v,available) for v in images))
    guides={}
    for lang in ['zh','en']:
        key='guide_'+lang;v=payload.get(key,old[key]);guides[key]=resolve(v,[old[key]]) if v else ''
    descriptions={key:str(payload.get(key,old[key])).strip()[:5000] for key in ['description_zh','description_en']}
    if re.search(r'[\u3400-\u9fff]',descriptions['description_en']):raise ValueError('英文产品描述不能包含中文')
    # 内容寻址新文件，不覆盖或删除原图；历史报价仍可读取原文件。
    for name,raw in pending.items():
        path=STATE/'images'/name
        if not path.exists():
            with path.open('xb') as f:f.write(raw)
    c.execute('INSERT INTO product_content VALUES(?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET images=excluded.images,description_zh=excluded.description_zh,description_en=excluded.description_en,guide_zh=excluded.guide_zh,guide_en=excluded.guide_en',(p['code'],json.dumps(names),descriptions['description_zh'],descriptions['description_en'],guides['guide_zh'],guides['guide_en']))
    c.execute('UPDATE products SET photo=? WHERE code=?',(names[0],p['code']))
    return {'ok':True,'content':product_content(p,c)}

def product_public(p,c,user,admin=False):
    currency=user['currency'] if user else 'USD';s=settings(c);vs=c.execute('SELECT * FROM variants WHERE code=?',(p['code'],)).fetchall()
    vs=sorted(vs,key=lambda v:(SIZES.index(v['size']) if v['size'] in SIZES else 999,v['color'] or '',v['sku']))
    variants=[]
    for v in vs:
        if not v['price'] or v['price']<=0:continue
        row={'sku':v['sku'],'color':v['color'],'colorEn':translate_color(v['color'] or '',v['sku']),'size':v['size'],'inStock':v['available'] is not None and v['available']>0,'price':unit_price(v['price'],currency,0,s),'tiers':[unit_price(v['price'],currency,q,s) for q in [100,300,500]]}
        if admin:row['available']=v['available']
        variants.append(row)
    result={'code':p['code'],'nameZh':p['name_zh'],'nameEn':product_name_en(p['code'],p['name_en']),'category':p['category'],'categoryIds':category_ids(c,p['code']),'image':'/api/products/'+p['code']+'/image' if p['photo'] or p['image_url'] else None,'variants':variants,'currency':currency,'inStock':any(v['inStock'] for v in variants)}
    content=product_content(p,c)
    result.update(images=['/api/products/'+p['code']+'/gallery/'+f for f in content['images']],descriptionZh=content['description_zh'],descriptionEn=content['description_en'],guideZh=('/api/products/'+p['code']+'/gallery/'+content['guide_zh']) if content['guide_zh'] else None,guideEn=('/api/products/'+p['code']+'/gallery/'+content['guide_en']) if content['guide_en'] else None)
    if result['images']:result['image']=result['images'][0]
    else:result['images']=[result['image']] if result['image'] else []
    result['translations']={'name':{'zh':result['nameZh'],'en':result['nameEn']}}
    if admin:result.update(published=bool(p['published']),featured=bool(p['featured']),position=p['position'],hasEnglish=has_product_name(p['code'],p['name_en']),sourceCategory=p['source_category'],translationPending=any(color_name_en(v['color'],v['sku']) is None for v in vs))
    return result

def quote_build(c,user,payload):
    lines=payload.get('lines',[])
    if not isinstance(lines,list) or not 1<=len(lines)<=500:raise ValueError('请选择产品，单次最多500条规格')
    quantities=Counter()
    for l in lines:
        if not isinstance(l,dict) or not isinstance(l.get('sku'),str):raise ValueError('选款资料无效')
        quantities[l['sku']]+=integer(l.get('quantity'),1,100000)
    records=[];bycode=Counter();s=settings(c);currency=user['currency']
    for sku,qty in quantities.items():
        r=c.execute('SELECT v.*,p.name_zh,p.name_en,p.photo,p.published,p.present FROM variants v JOIN products p ON p.code=v.code WHERE sku=?',(sku,)).fetchone()
        if not r or not r['published'] or not r['present']:raise ValueError('部分产品已下架，请重新选款')
        if r['available'] is None or r['available']<=0:raise ValueError(f"{r['name_zh']} {r['size']}：暂无现货，请重新选款或联系我们")
        if not r['price'] or r['price']<=0 or not r['photo'] or not has_product_name(r['code'],r['name_en']):raise ValueError('部分产品资料待完善，请联系我们报价')
        records.append((r,qty));bycode[r['code']]+=qty
    if currency=='USD':
        if any(q<s['fob']['styleMoq'] for q in bycode.values()):raise ValueError(f"每款至少订购 {s['fob']['styleMoq']} 件，尺码可混搭")
        if sum(bycode.values())<s['fob']['overallMoq']:raise ValueError(f"整单至少订购 {s['fob']['overallMoq']} 件")
    base=money(sum(Decimal(str(r['price']))*qty for r,qty in records))
    cn=s['cn'];rate=cn['tier3Rate'] if base>=cn['tier3Amount'] else cn['tier2Rate'] if base>=cn['tier2Amount'] else 1
    if currency=='CNY' and base<cn['minimumOrderAmount']:raise ValueError(f"人民币订单至少 ¥{cn['minimumOrderAmount']:,.0f}")
    source=c.execute("SELECT value FROM metadata WHERE key='source_time'").fetchone()
    if not source or not source[0]:raise ValueError('库存资料时间待确认，请先联系工作人员')
    try:
        dt=datetime.fromisoformat(source[0].replace('Z','+00:00'))
        if not dt.tzinfo:dt=dt.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
        current=datetime.now(ZoneInfo('Asia/Shanghai'))
        stale=(current.hour,current.minute)>=(5,30) and dt.astimezone(ZoneInfo('Asia/Shanghai')).date()!=current.date()
    except ValueError:raise ValueError('库存资料时间待确认，请先联系工作人员')
    if stale:raise ValueError('库存资料需要更新，请联系工作人员')
    out=[]
    for r,qty in records:
        price=unit_price(r['price'],currency,bycode[r['code']],s)
        if currency=='CNY':price=money(Decimal(str(r['price']))*Decimal(str(rate)))
        out.append({'code':r['code'],'sku':r['sku'],'nameZh':r['name_zh'],'nameEn':product_name_en(r['code'],r['name_en']),'color':r['color'],'colorEn':translate_color(r['color'] or '',r['sku']),'size':r['size'],'quantity':qty,'unitPrice':price,'amount':money(Decimal(str(price))*qty),'image':r['photo'],'unitWeightG':r['weight'],'cartonQty':r['carton_qty'],'cartonSize':r['carton_size']})
    return {'currency':currency,'lines':out,'quantity':sum(bycode.values()),'total':money(sum(Decimal(str(x['amount'])) for x in out)),'buyer':public_user(user),'createdAt':now(),'sourceTime':source[0],'language':normalize_language(payload.get('language')),'company':'Kunshan Jiayuan Garment & Clothing Co., Ltd.','companyZh':'昆山加元服装服饰有限公司','languageVersion':2,'packingNote':document_messages(payload.get('language'))['packing']}

def quote_record(row):
    d=json.loads(row['snapshot']);d.update(id=row['id'],number=row['number'],firstInquiry=bool(row['first_inquiry']),unread=bool(row['unread']),status=row['status'])
    for l in d['lines']:l['image']='/api/quotes/'+str(row['id'])+'/image/'+l['code']
    return d

class Handler(BaseHTTPRequestHandler):
    server_version='PETCIRCLE'
    def log_message(self,*args):pass
    def send_bytes(self,data,content='application/json; charset=utf-8',status=200,headers=None):
        self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','same-origin')
        self.send_header('Cache-Control','no-store' if self.path.startswith('/api') else 'public, max-age=3600')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)
    def reply(self,obj,status=200,headers=None):self.send_bytes(json.dumps(obj,ensure_ascii=False).encode(),status=status,headers=headers)
    def user(self,c,required=False,admin=False):
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie','')); token=cookie.get('petcircle_session');u=None
        if token:
            u=c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(hashlib.sha256(token.value.encode()).hexdigest(),time.time())).fetchone()
        if (required and not u) or (admin and (not u or u['role']!='admin')):raise PermissionError('请先登录管理员账号' if admin else '请先注册或登录')
        return u
    def read_json(self):
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:raise ValueError('请求资料无效')
        if not 0<n<=(60*1024*1024 if self.path.split('?')[0]=='/api/admin/product-content' else 2*1024*1024):raise ValueError('提交内容过大或为空')
        d=json.loads(self.rfile.read(n))
        if not isinstance(d,dict):raise ValueError('请求资料无效')
        return d
    def do_GET(self):self.handle_api(False)
    def do_POST(self):self.handle_api(True)
    def handle_api(self,write):
        try:
            parsed=urlparse(self.path);path=unquote(parsed.path);q=parse_qs(parsed.query)
            if write:
                origin=self.headers.get('Origin')
                if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise PermissionError('请从本站页面提交')
            with connect() as c:
                user=self.user(c); payload=self.read_json() if write else {}
                if path=='/api/health':return self.reply({'ok':True})
                if path=='/api/messages' and write:
                    key=str(payload.get('requestKey',''))
                    if not re.fullmatch(r'[a-zA-Z0-9-]{12,100}',key):raise ValueError('请刷新页面后重新提交')
                    fields={}
                    for name,limit in [('name',100),('email',254),('phone',100),('wechat',100),('company',200),('message',3000),('source',200)]:
                        value=payload.get(name,'')
                        if not isinstance(value,str) or len(value)>limit:raise ValueError('留言内容过长，请精简后提交')
                        fields[name]=value.strip()
                    if not fields['name']:raise ValueError('请填写姓名')
                    if not any(fields[k] for k in ['email','phone','wechat']):raise ValueError('请至少填写一种联系方式')
                    if fields['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',fields['email']):raise ValueError('请填写有效邮箱')
                    if fields['phone'] and len(re.sub(r'\D','',fields['phone']))<6:raise ValueError('请填写有效电话或WhatsApp号码')
                    if c.execute('SELECT 1 FROM messages WHERE request_key=?',(key,)).fetchone():return self.reply({'ok':True})
                    with ATTEMPT_LOCK:
                        ip=self.client_address[0];MESSAGE_ATTEMPTS[ip]=[stamp for stamp in MESSAGE_ATTEMPTS[ip] if stamp>time.time()-600]
                        if len(MESSAGE_ATTEMPTS[ip])>=10:return self.reply({'error':'提交次数较多，请稍后再试'},429)
                        MESSAGE_ATTEMPTS[ip].append(time.time())
                    c.execute('INSERT OR IGNORE INTO messages(name,email,phone,wechat,company,message,language,source,created_at,request_key) VALUES(?,?,?,?,?,?,?,?,?,?)',(*[fields[k] for k in ['name','email','phone','wechat','company','message']], normalize_language(payload.get('language')),fields['source'],now(),key))
                    return self.reply({'ok':True},201)
                if path=='/api/me':return self.reply({'user':public_user(user) if user else None})
                if write and path in ['/api/login','/api/register']:
                    with ATTEMPT_LOCK:
                        ip=self.client_address[0];ATTEMPTS[ip]=[t for t in ATTEMPTS[ip] if t>time.time()-300]
                        if len(ATTEMPTS[ip])>=25:return self.reply({'error':'尝试次数过多，请稍后再试'},429)
                        ATTEMPTS[ip].append(time.time())
                    email=str(payload.get('email','')).strip().lower();password=str(payload.get('password',''))
                    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:raise ValueError('请填写有效邮箱')
                    if not 10<=len(password)<=128:raise ValueError('密码需为10至128个字符')
                    if path=='/api/register':
                        fields=[str(payload.get(k,'')).strip()[:200] for k in ['contact','company','country']]
                        if not all(fields):raise ValueError('请填写联系人、公司和国家／地区')
                        if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():raise ValueError('该邮箱已注册，请登录')
                        c.execute('INSERT INTO users(email,password,contact,company,country,phone,created_at) VALUES(?,?,?,?,?,?,?)',(email,hash_password(password),*fields,str(payload.get('phone',''))[:100],now()))
                    else:
                        u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                        if not u or not password_matches(password,u['password']):raise ValueError('邮箱或密码不正确')
                    u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone();token=secrets.token_urlsafe(32)
                    c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+7*86400))
                    return self.reply({'user':public_user(u)},headers={'Set-Cookie':f'petcircle_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800'})
                if write and path=='/api/logout':
                    cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
                    if cookie.get('petcircle_session'):c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(cookie['petcircle_session'].value.encode()).hexdigest(),))
                    return self.reply({'ok':True},headers={'Set-Cookie':'petcircle_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'})
                if write and path=='/api/profile':
                    user=self.user(c,True); fields=[str(payload.get(k,'')).strip()[:200] for k in ['contact','company','country']]
                    if not all(fields):raise ValueError('请填写联系人、公司和国家／地区')
                    c.execute('UPDATE users SET contact=?,company=?,country=?,phone=? WHERE id=?',(*fields,str(payload.get('phone',''))[:100],user['id']))
                    return self.reply({'user':public_user(c.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone())})
                if path=='/api/categories' and not write:return self.reply({'categories':list_categories(c)})
                if path=='/api/stock-check' and write:
                    lines=payload.get('lines',[])
                    if not isinstance(lines,list) or len(lines)>100:raise ValueError('请核对选款数量')
                    results=[]
                    for l in lines:
                        qty=integer(l.get('quantity'),1,100000);r=c.execute('SELECT v.sku,v.available FROM variants v JOIN products p ON p.code=v.code WHERE v.sku=? AND p.published=1 AND p.present=1',(str(l.get('sku','')),)).fetchone()
                        results.append({'sku':l.get('sku'),'ok':bool(r and r['available'] is not None and r['available']>0)})
                    return self.reply({'results':results})
                if path=='/api/products' and not write:
                    admin=q.get('admin')==['1']
                    if admin:self.user(c,True,True)
                    sql='SELECT * FROM products WHERE present=1'+('' if admin else ' AND published=1');args=[]
                    if q.get('category',[''])[0]:
                        sql+=' AND code IN (SELECT pc.code FROM product_categories pc JOIN categories t ON t.id=pc.category_id WHERE t.active=1 AND (t.id=? OR t.parent_id=?))';args.extend([q['category'][0]]*2)
                    if admin and q.get('unclassified')==['1']:sql+=' AND NOT EXISTS (SELECT 1 FROM product_categories pc JOIN categories t ON t.id=pc.category_id WHERE pc.code=products.code AND t.active=1)'
                    if admin and q.get('directCategory',[''])[0]:sql+=' AND code IN (SELECT code FROM product_categories WHERE category_id=?)';args.append(q['directCategory'][0])
                    if admin and q.get('published',[''])[0]:
                        state=q['published'][0]
                        if state not in ['0','1']:raise ValueError('请选择有效上架状态')
                        sql+=' AND published=?';args.append(int(state))
                    if admin and q.get('sourceCategory',[''])[0]:sql+=' AND source_category=?';args.append(q['sourceCategory'][0])
                    if q.get('search',[''])[0]:sql+=' AND (name_zh LIKE ? OR name_en LIKE ? OR code LIKE ?)';args+=['%'+q['search'][0][:100]+'%']*3
                    if q.get('featured')==['1']:sql+=' AND featured=1'
                    page=max(1,min(1000,int(q.get('page',['1'])[0])));limit=24 if admin else 12
                    total=c.execute('SELECT count(*) FROM ('+sql+')',args).fetchone()[0]
                    products=[product_public(p,c,user,admin) for p in c.execute(sql+' ORDER BY position,code LIMIT ? OFFSET ?',args+[limit,(page-1)*limit])]
                    return self.reply({'products':products,'total':total,'page':page,'pages':max(1,math.ceil(total/limit)),**({'sourceCategories':[r[0] for r in c.execute('SELECT DISTINCT source_category FROM products WHERE present=1 ORDER BY source_category')]} if admin else {})})
                if path.startswith('/api/products/'):
                    code=path.split('/')[3];p=c.execute('SELECT * FROM products WHERE code=?',(code,)).fetchone()
                    if not p or not p['present'] or (not p['published'] and (not user or user['role']!='admin')):return self.reply({'error':'产品暂未上架'},404)
                    if '/gallery/' in path:
                        filename=path.rsplit('/',1)[-1]
                        content=product_content(p,c)
                        allowed=content['images']+[content['guide_zh'],content['guide_en']]
                        if user and user['role']=='admin':allowed += [r[0] for r in c.execute('SELECT filename FROM product_image_candidates WHERE code=?',(code,))]
                        if filename not in allowed:return self.reply({'error':'图片不存在'},404)
                        return self.send_bytes((STATE/'images'/filename).read_bytes(),'image/jpeg')
                    if path.endswith('/image'):
                        if not p['photo'] and not p['image_url']:return self.reply({'error':'图片待完善'},404)
                        photo=STATE/'images'/ensure_image(p,c)
                        return self.send_bytes(photo.read_bytes(),'image/jpeg')
                    return self.reply({'product':product_public(p,c,user)})
                if write and path in ['/api/quote-preview','/api/quotes']:
                    user=self.user(c,True)
                    if path=='/api/quote-preview':
                        preview=quote_build(c,user,payload)
                        for l in preview['lines']:l.pop('image',None)
                        return self.reply({'quote':preview})
                    key=str(payload.get('requestKey',''))
                    if not re.fullmatch(r'[a-zA-Z0-9-]{12,100}',key):raise ValueError('请刷新页面后重新提交')
                    c.execute('BEGIN IMMEDIATE')
                    old=c.execute('SELECT * FROM quotes WHERE user_id=? AND request_key=?',(user['id'],key)).fetchone()
                    if old:return self.reply({'quote':quote_record(old)})
                    quote=quote_build(c,user,payload)
                    for l in quote['lines']:
                        src=STATE/'images'/l['image'];digest=hashlib.sha256(src.read_bytes()).hexdigest()+'.jpg';dst=STATE/'quote-images'/digest
                        if not dst.exists():shutil.copy2(src,dst)
                        l['image']=digest
                    first=not c.execute('SELECT 1 FROM quotes WHERE user_id=?',(user['id'],)).fetchone();num='PC'+datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')+'-'+secrets.token_hex(4).upper();quote['number']=num
                    c.execute('INSERT INTO quotes(user_id,number,snapshot,total,quantity,currency,first_inquiry,created_at,request_key) VALUES(?,?,?,?,?,?,?,?,?)',(user['id'],num,json.dumps(quote,ensure_ascii=False),quote['total'],quote['quantity'],quote['currency'],first,now(),key))
                    return self.reply({'quote':quote_record(c.execute('SELECT * FROM quotes WHERE number=?',(num,)).fetchone())},201)
                if path=='/api/quotes' and not write:
                    user=self.user(c,True);rows=c.execute('SELECT * FROM quotes WHERE user_id=? ORDER BY id DESC',(user['id'],)).fetchall()
                    return self.reply({'quotes':[quote_record(r) for r in rows]})
                if path.startswith('/api/quotes/'):
                    user=self.user(c,True);parts=path.split('/');qid=int(parts[3]);r=c.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
                    if not r or (user['role']!='admin' and r['user_id']!=user['id']):return self.reply({'error':'未找到报价单'},404)
                    if len(parts)>4 and parts[4]=='image':
                        data=json.loads(r['snapshot']);line=next((l for l in data['lines'] if l['code']==parts[5]),None)
                        if not line:return self.reply({'error':'图片不存在'},404)
                        return self.send_bytes((STATE/'quote-images'/line['image']).read_bytes(),'image/jpeg')
                    if len(parts)>4 and parts[4] in ['pdf','xlsx']:
                        from server.exports import export_quote
                        data,ctype=export_quote(json.loads(r['snapshot']),parts[4],STATE)
                        return self.send_bytes(data,ctype,headers={'Content-Disposition':f'attachment; filename="{r["number"]}.{parts[4]}"'})
                    if user['role']=='admin':c.execute('UPDATE quotes SET unread=0 WHERE id=?',(qid,));r=c.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
                    return self.reply({'quote':quote_record(r)})
                if path.startswith('/api/admin/'):
                    user=self.user(c,True,True)
                    if path=='/api/admin/sync' and not write:return self.reply(dict(SYNC_STATE))
                    if path=='/api/admin/sync' and write:
                        with SYNC_LOCK:
                            if not SYNC_STATE['running']:
                                SYNC_STATE.update(running=True,error='',result=None)
                                threading.Thread(target=sync_formal,daemon=True).start()
                        return self.reply({'running':True})
                    if path=='/api/admin/summary':return self.reply({'products':c.execute('SELECT count(*) FROM products WHERE present=1').fetchone()[0],'published':c.execute('SELECT count(*) FROM products WHERE present=1 AND published=1').fetchone()[0],'unread':c.execute('SELECT count(*) FROM quotes WHERE unread=1').fetchone()[0],'unreadMessages':c.execute('SELECT count(*) FROM messages WHERE unread=1').fetchone()[0],'sourceTime':dict(c.execute('SELECT key,value FROM metadata WHERE key IN (\'source_time\',\'imported_at\')').fetchall())})
                    if path=='/api/admin/messages' and not write:
                        page=max(1,min(100000,int(q.get('page',['1'])[0])));total=c.execute('SELECT count(*) FROM messages').fetchone()[0]
                        rows=[dict(r) for r in c.execute('SELECT * FROM messages ORDER BY unread DESC,id DESC LIMIT 50 OFFSET ?',((page-1)*50,))]
                        for row in rows:row.pop('request_key',None)
                        return self.reply({'messages':rows,'pages':max(1,math.ceil(total/50))})
                    if path=='/api/admin/messages' and write:
                        mid=integer(payload.get('id'),1)
                        if not c.execute('SELECT 1 FROM messages WHERE id=?',(mid,)).fetchone():return self.reply({'error':'未找到留言'},404)
                        c.execute('UPDATE messages SET unread=0 WHERE id=?',(mid,));return self.reply({'ok':True})
                    if path=='/api/admin/products' and write:
                        codes=payload.get('codes',[])
                        if not isinstance(codes,list) or not 1<=len(codes)<=500:raise ValueError('请选择产品')
                        changes=payload.get('changes',{});allowed={k:v for k,v in changes.items() if k in ['published','featured','position','category','categoryIds']}
                        if not allowed:raise ValueError('请选择要修改的内容')
                        for code in codes:
                            p=c.execute('SELECT * FROM products WHERE code=? AND present=1',(code,)).fetchone()
                            if not p:raise ValueError('产品不存在')
                            if allowed.get('published'):
                                if not has_product_name(p['code'],p['name_en']):raise ValueError(f"本批次未上架：{p['code']} · {p['name_zh']}，请先完善英文品名")
                                if any(color_name_en(v['color'],v['sku']) is None for v in c.execute('SELECT color,sku FROM variants WHERE code=? AND price>0',(code,))):raise ValueError(f"本批次未上架：{p['code']} · {p['name_zh']}，请先完善英文规格名称")
                                try:
                                    ensure_image(p,c)
                                except Exception:
                                    if not p['image_url']:reason='缺少产品图片，请上传或选择ERP图片'
                                    elif urlparse(p['image_url']).hostname not in TRUSTED_IMAGES:reason='图片来源暂不支持，请重新选图或上传'
                                    else:reason='图片暂时无法读取，请重新选图或上传'
                                    raise ValueError(f"本批次未上架：{p['code']} · {p['name_zh']}，{reason}") from None
                                if not c.execute('SELECT 1 FROM variants WHERE code=? AND price>0 AND available IS NOT NULL',(code,)).fetchone():raise ValueError(f"本批次未上架：{p['code']} · {p['name_zh']}，产品规格或价格待完善")
                            if 'category' in allowed and allowed['category'] and not c.execute('SELECT 1 FROM categories WHERE id=? AND active=1',(allowed['category'],)).fetchone():raise ValueError('请选择有效分类')
                            if 'categoryIds' in allowed or 'category' in allowed:
                                ids=allowed.get('categoryIds', [allowed['category']] if allowed.get('category') else [])
                                set_product_categories(c,code,ids,changes.get('categoryMode','replace'))
                            for k,v in allowed.items():
                                if k in ['category','categoryIds']:continue
                                val=integer(v,0,99999) if k=='position' else int(bool(v)) if k in ['published','featured'] else str(v)
                                c.execute(f'UPDATE products SET {k}=? WHERE code=?',(val,code))
                        return self.reply({'ok':True})
                    if path=='/api/admin/product-content' and not write:
                        p=c.execute('SELECT * FROM products WHERE code=? AND present=1',(q.get('code',[''])[0],)).fetchone()
                        if not p:raise ValueError('产品不存在')
                        return self.reply({'content':product_content(p,c),'erpImages':[r[0] for r in c.execute('SELECT filename FROM product_image_candidates WHERE code=?',(p['code'],))]})
                    if path=='/api/admin/product-erp-images' and write:
                        return self.reply(pull_erp_images(c,str(payload.get('code',''))))
                    if path=='/api/admin/product-content' and write:
                        return self.reply(save_product_content(c,payload))
                    if path=='/api/admin/categories' and write:
                        if payload.get('replace') is True:
                            base=payload.get('baseIds')
                            if not isinstance(base,list) or set(base)!={r[0] for r in c.execute('SELECT id FROM categories WHERE active=1')}:raise ValueError('分类已更新，请刷新后再保存')
                        save_categories(c,payload.get('categories',[]),payload.get('replace') is True)
                        return self.reply({'ok':True})
                    if path=='/api/admin/customers' and not write:
                        return self.reply({'customers':[public_user(u) for u in c.execute("SELECT * FROM users WHERE role='customer' ORDER BY id DESC")]})
                    if path=='/api/admin/customers' and write:
                        currency=payload.get('currency')
                        if currency not in ['USD','CNY']:raise ValueError('请选择报价币种')
                        c.execute("UPDATE users SET currency=? WHERE id=? AND role='customer'",(currency,integer(payload.get('id'),1)))
                        return self.reply({'ok':True})
                    if path=='/api/admin/quotes' and not write:return self.reply({'quotes':[quote_record(r) for r in c.execute('SELECT * FROM quotes ORDER BY unread DESC,id DESC')]})
                    if path=='/api/admin/quotes' and write:
                        if payload.get('status') not in ['pending','following','closed']:raise ValueError('请选择跟进状态')
                        c.execute('UPDATE quotes SET status=? WHERE id=?',(payload['status'],integer(payload.get('id'),1)));return self.reply({'ok':True})
                if path.startswith('/media/'):
                    parts=path.split('/');section=parts[2] if len(parts)>2 else '';name=parts[3] if len(parts)==4 else ''
                    allowed=['petcircle-garden.png'] if section=='hero' else [r['image'] for r in json.loads((ROOT/'assets/production/materials.json').read_text())] if section=='production' else ['knitwear.jpg','coats.jpg','sweatshirts.jpg'] if section=='editorial' else ['size-guide-cn.jpeg','size-guide-en.jpeg'] if section=='guides' else []
                    if name not in allowed:return self.reply({'error':'未找到图片'},404)
                    p=ROOT/'assets'/section/name;return self.send_bytes(p.read_bytes(),mimetypes.guess_type(name)[0] or 'image/png')
                return self.reply({'error':'未找到内容'},404)
        except PermissionError as e:self.reply({'error':str(e)},403)
        except (ValueError,KeyError,TypeError,IndexError,json.JSONDecodeError) as e:self.reply({'error':str(e) if isinstance(e,ValueError) else '提交资料不完整，请检查后重试'},400)
        except Exception:
            import traceback;traceback.print_exc();self.reply({'error':'暂时无法完成，请稍后重试或联系我们'},500)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8790);ap.add_argument('--sync',action='store_true');args=ap.parse_args();init()
    if args.sync:print(json.dumps(sync(),ensure_ascii=False))
    else:
        if not DB.exists():init()
        print(f'PETCIRCLE backend: http://127.0.0.1:{args.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
