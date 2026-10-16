import businessMessages from '../../shared/business-messages.json' with {type:'json'};
import {productName} from './i18n';
export const api=async(path,body)=>{const r=await fetch('/api'+path,{credentials:'same-origin',...(body!==undefined?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw Error(d.error||'操作未完成，请稍后重试');return d};
export const stored=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}};
export const money=(n,c='USD')=>new Intl.NumberFormat(c==='CNY'?'zh-CN':'en-US',{style:'currency',currency:c}).format(n);
export const pname=productName;
export const date=s=>new Date(s).toLocaleString();
export const statuses={pending:['待跟进','To follow up'],following:['跟进中','Following up'],closed:['已结束','Closed']};
export function englishError(s){if(businessMessages[s])return businessMessages[s];if(s.includes('暂无现货'))return 'This item is out of stock. Choose another item or contact us.';if(s.includes('请先完善英文规格名称'))return 'Please review the English variant names before publishing.';if(s.includes('请先完善英文品名'))return 'Please complete the English product name first.';let n=s.match(/每款至少订购 ([\d,]+)/);if(n)return `Minimum ${n[1]} pieces per style. Colors and sizes may be mixed.`;n=s.match(/整单至少订购 ([\d,]+)/);if(n)return `Minimum ${n[1]} pieces per order.`;n=s.match(/人民币订单至少 ¥([\d,.]+)/);if(n)return `Minimum order value: CNY ${n[1]}.`;return 'Please check your selection and try again, or contact us.';}
