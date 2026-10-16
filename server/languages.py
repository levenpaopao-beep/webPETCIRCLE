"""前后台共用语言预设；草稿语言不可通过接口提前开放。"""
import json
from pathlib import Path
CONFIG=json.loads((Path(__file__).resolve().parents[1]/'shared/languages.json').read_text())
def normalize_language(code):
    return next((row['code'] for row in CONFIG['languages'] if row['code']==code and row['enabled']),CONFIG['default'])
def localized(values,code,fallback=''):
    return values.get(code) or values.get(CONFIG['fallback']) or fallback

DOCUMENT_MESSAGES=json.loads((Path(__file__).resolve().parents[1]/'shared/document-messages.json').read_text())
def document_messages(code):
    return {**DOCUMENT_MESSAGES[CONFIG['fallback']],**{k:v for k,v in DOCUMENT_MESSAGES.get(normalize_language(code),{}).items() if v}}

PRODUCT_TEXT=json.loads((Path(__file__).resolve().parents[1]/'shared/product-translations.json').read_text())
def valid_english_name(value):
    import re
    return bool(value and re.search('[A-Za-z]',value) and not re.search('[\u3400-\u9fff]',value))
def product_name_en(code,value):
    return PRODUCT_TEXT['names'].get(code) or (value if valid_english_name(value) else 'PETCIRCLE '+code)
def color_name_en(value,sku=''):
    """词组优先；未知规格保留唯一业务编号，绝不伪装为混色。"""
    import re
    if sku in PRODUCT_TEXT['variants']:return PRODUCT_TEXT['variants'][sku]
    raw=str(value or '').strip()
    if not raw:return ''
    colors=PRODUCT_TEXT['colors']
    if raw in colors:return colors[raw]
    if not re.search('[\u3400-\u9fff]',raw):return raw
    text=re.sub(r'\s*(?:one\s*size|onesize)$','',raw,flags=re.I).strip()
    suffix=''
    match=re.search(r'(?:色)?[-/]?(XXS|XS|S|M|L|XL|XXL|[2-8]L|MD)$',text,re.I)
    if match:suffix=' / '+match[1].upper();text=text[:match.start()]
    if text in colors:return colors[text]+suffix
    if text.endswith('色') and text[:-1] in colors:return colors[text[:-1]]+suffix
    patterns={'条纹':'stripes','条':'stripes','格':'plaid','波点':'polka dots','点点':'polka dots','点':'polka dots','豹纹':'leopard print','豹':'leopard print','帽子':'hat','帽':'hat','边':'trim','底':'base'}
    pattern=''
    for ending,label in patterns.items():
        if text.endswith(ending):text=text[:-len(ending)];pattern=' '+label;break
    tokens=[]
    while text:
        if text[0] in '+/、 ':text=text[1:];continue
        word=next((x for x in sorted(colors,key=len,reverse=True) if text.startswith(x)),None)
        if not word:break
        tokens.append(colors[word]);text=text[len(word):]
    if not text and tokens:return ' & '.join(tokens)+pattern+suffix
    if raw.startswith('夜光'):
        tail=color_name_en(raw[2:])
        if tail:return 'Glow-in-the-dark '+tail.lower()
    return None

def has_product_name(code,value):
    return code in PRODUCT_TEXT['names'] or valid_english_name(value)
