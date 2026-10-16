import test from 'node:test';
import assert from 'node:assert/strict';
import {enabledLanguages,languages,normalizeLanguage,translator,localized,productName,catalogs} from '../src/i18n.js';
test('四种预设，只开放中英文；非法或草稿偏好回到英文',()=>{
 assert.deepEqual(languages.map(l=>l.code),['zh','en','ru','es']);
 assert.deepEqual(enabledLanguages.map(l=>l.code),['zh','en']);
 for(const value of ['ru','es','fr',null,{},''])assert.equal(normalizeLanguage(value),'en');
});
test('全部固定页面文案有中英文；俄西草稿为空并逐条回退英文',()=>{
 assert.ok(Object.keys(catalogs.en).length>180);
 for(const key of Object.keys(catalogs.en)){
  assert.ok(catalogs.zh[key],key);
  for(const lang of ['ru','es'])assert.equal(translator(lang)(key),catalogs.en[key]);
 }
 assert.equal(translator('zh')('Sign in'),'登录');
 assert.equal(translator('en')('中文动态内容','Dynamic English'),'Dynamic English');
});
test('产品和长篇内容缺少翻译时回退英文，支持后续增加产品翻译',()=>{
 const p={code:'A',nameZh:'毛衣',nameEn:'Sweater',translations:{name:{en:'Sweater',ru:'Свитер'}}};
 assert.equal(productName(p,'ru'),'Свитер');
 assert.equal(productName(p,'es'),'Sweater');
 assert.equal(productName({code:'B'},'ru'),'B');
 assert.deepEqual(localized({en:['About']},'ru'),['About']);
});
