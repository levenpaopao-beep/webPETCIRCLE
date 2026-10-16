import config from '../../shared/languages.json' with {type:'json'};
import zh from './locales/zh.json' with {type:'json'};
import en from './locales/en.json' with {type:'json'};
import ru from './locales/ru.json' with {type:'json'};
import es from './locales/es.json' with {type:'json'};
export const languages=config.languages;
export const enabledLanguages=languages.filter(l=>l.enabled);
export const catalogs={zh,en,ru,es};
export const normalizeLanguage=(code,includeDrafts=false)=>languages.find(l=>l.code===code&&(includeDrafts||l.enabled))?.code||config.default;
export const languageInfo=code=>languages.find(l=>l.code===normalizeLanguage(code));
export function localized(values,code,fallback=''){
 const requested=normalizeLanguage(code,true);
 return values?.[requested]||values?.[config.fallback]||fallback;
}
// 支持动态业务文案传入中英文；固定页面文案统一从语言文件读取。
export const translator=code=>(key,english)=>english!==undefined
 ? localized({zh:key,en:english,...(catalogs[code]?.[english]?{[code]:catalogs[code][english]}:{})},code,english)
 : localized(Object.fromEntries(Object.entries(catalogs).map(([lang,entries])=>[lang,entries[key]])),code,key);
export const productName=(product,code)=>localized(product.translations?.name,code,localized({zh:product.nameZh,en:product.nameEn},code,product.code));

export const sizeLabel=(value,lang)=>/^(均码|one\s*size)$/i.test(String(value).trim())?translator(lang)('One size'):value;
