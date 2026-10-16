import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {parse} from '@babel/parser';
import {translator,sizeLabel,catalogs} from '../src/i18n.js';
const root=new URL('../src/',import.meta.url);
const files=fs.readdirSync(root).filter(f=>f.endsWith('.jsx'));
const allowed=/^(PETCIRCLE|WhatsApp|levenwong@foxmail\.com|WhatsApp \+852 8483 1068|: levenwong|© 2026 PETCIRCLE ·|levenwong ·)$/;
function inspect(node,issues,file){if(!node||typeof node!=='object')return;if(node.type==='FunctionDeclaration'&&['AdminMessages','CategoryManager'].includes(node.id?.name))return;
 if(node.type==='JSXText'&&/[A-Za-z\u3400-\u9fff]/.test(node.value)&&!allowed.test(node.value.trim()))issues.push(`${file}:${node.loc.start.line} 裸文字 ${node.value.trim()}`);
 if(node.type==='JSXAttribute'&&['aria-label','placeholder','title'].includes(node.name?.name)&&node.value?.type==='StringLiteral'&&/[A-Za-z\u3400-\u9fff]/.test(node.value.value))issues.push(`${file}:${node.loc.start.line} 辅助文字未翻译`);
 if(node.type==='CallExpression'&&node.callee.type==='Identifier'&&node.callee.name==='t'&&node.arguments.length===1&&node.arguments[0].type==='StringLiteral')for(const lang of ['en','zh'])if(!catalogs[lang][node.arguments[0].value])issues.push(`${file}:${node.loc.start.line} 缺少${lang}翻译 ${node.arguments[0].value}`);
 for(const value of Object.values(node)){if(Array.isArray(value))value.forEach(x=>inspect(x,issues,file));else if(value&&typeof value==='object')inspect(value,issues,file)}
}
test('页面新增文字必须进入中英字典，禁止残留裸文字与辅助标签',()=>{const issues=[];for(const file of files.filter(f=>f!=='admin.jsx'))inspect(parse(fs.readFileSync(new URL(file,root),'utf8'),{sourceType:'module',plugins:['jsx']}),issues,file);assert.deepEqual(issues,[])});
test('品牌、联系人与已确认业务术语不混用',()=>{const t=translator('en');assert.match(t('Your next collection.\nYour name on it.'),/your brand/);assert(!/your name on it/i.test(t('Your next collection.\nYour name on it.')));assert.equal(t('Name *'),'Name *');assert.equal(t('Email us'),'Email us');assert.equal(t('To confirm'),'Subject to confirmation');assert.equal(translator('zh')('Kunshan, China'),'中国 · 昆山')});
test('均码显示翻译不改其他尺码',()=>{for(const input of ['均码','one size','One Size','onesize']){assert.equal(sizeLabel(input,'en'),'One size');assert.equal(sizeLabel(input,'zh'),'均码')}for(const input of ['XS','XL','2L'])assert.equal(sizeLabel(input,'en'),input)});
test('联系入口不得声称直接发邮件或收图',()=>{for(const file of ['pages.jsx','oem.jsx']){const source=fs.readFileSync(new URL(file,root),'utf8');assert(!/t\("Email us(?: your references)?"\)/.test(source));assert(!/href="(?:mailto:|https:\/\/wa\.me)/.test(source))}});
