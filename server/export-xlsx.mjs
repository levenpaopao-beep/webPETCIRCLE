import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input,output]=process.argv.slice(2);
const {quote:q,imageRoot}=JSON.parse(await fs.readFile(input,'utf8'));
const config=JSON.parse(await fs.readFile(new URL('../shared/languages.json',import.meta.url),'utf8'));
const language=config.languages.find(l=>l.code===q.language&&l.enabled)?.code||config.default;
const messages=JSON.parse(await fs.readFile(new URL('../shared/document-messages.json',import.meta.url),'utf8'));
const text={...messages[config.fallback],...Object.fromEntries(Object.entries(messages[language]||{}).filter(([,v])=>v))};
const zh=language==='zh', wb=Workbook.create(),sheet=wb.worksheets.add(text.sheet);
const literal=v=>typeof v==='string'&&/^[=+@-]/.test(v)?"'"+v:v;
const title=`PETCIRCLE | ${text.title} · ${q.number} · ${q.currency} · ${q.createdAt.slice(0,10)}`;
for(let row=1;row<=4;row++)sheet.getRange(`A${row}:K${row}`).merge();
sheet.getRange('A1').values=[[title]];
sheet.getRange('A2').values=[[zh?(q.companyZh||q.company):q.company]];
sheet.getRange('A3').values=[[literal(`${q.buyer.company} | ${q.buyer.contact} | ${q.buyer.email} | ${q.buyer.country}`)]];
sheet.getRange('A4').values=[[`levenwong@foxmail.com | WhatsApp +852 8483 1068 | ${text.wechat}: levenwong | +86 130 0324 6055`]];
const headings=text.xlsxHeads;
sheet.getRange('A5:K5').values=[headings];
sheet.getRange('A1:K3').format.font={name:'Arial',size:11};
sheet.getRange('A1:K4').format.rowHeight=25;
sheet.getRange('A1:K4').format.wrapText=true;
sheet.getRange('A1:K1').format.fill='#142D42';sheet.getRange('A1:K1').format.font={bold:true,color:'#FFFFFF',size:14};
sheet.getRange('A5:K5').format.wrapText=true;sheet.getRange('A5:K5').format.rowHeight=42;
sheet.getRange('A5:K5').format.fill='#E8ECEE';sheet.getRange('A5:K5').format.font={bold:true};
sheet.getRange('A:K').format.columnWidth=18;sheet.getRange('A:A').format.columnWidthPx=116;sheet.getRange('C:C').format.columnWidth=36;
for(let i=0;i<q.lines.length;i++){
  const l=q.lines[i],r=i+6;
  sheet.getRange(`A${r}:K${r}`).values=[['',l.code,zh?l.nameZh:l.nameEn,zh?l.color:l.colorEn,(/^(均码|one\s*size)$/i.test(l.size)?(zh?'均码':'One size'):l.size),l.quantity,l.unitPrice,l.amount,l.unitWeightG||null,l.cartonQty||null,l.cartonSize|| text.pending].map(literal)];
  sheet.getRange(`A${r}:K${r}`).format.rowHeightPx=110;sheet.getRange(`A${r}:K${r}`).format.wrapText=true;sheet.getRange(`A${r}:K${r}`).format.verticalAlignment='center';
  sheet.getRange(`H${r}`).formulas=[[`=ROUND(F${r}*G${r},2)`]];
  const b=await fs.readFile(imageRoot+'/'+l.image);
  sheet.images.add({dataUrl:'data:image/jpeg;base64,'+b.toString('base64'),anchor:{from:{row:r-1,col:0},extent:{widthPx:100,heightPx:100}}});
}
const last=q.lines.length+6;
sheet.getRange(`E${last}:H${last}`).values=[[text.sum,q.quantity,'',q.total]];
sheet.getRange(`H${last}`).formulas=[[`=ROUND(SUM(H6:H${last-1}),2)`]];
sheet.getRange(`G6:H${last}`).setNumberFormat('0.00');
sheet.getRange(`A${last+2}:K${last+2}`).merge();
sheet.getRange(`A${last+2}`).values=[[q.packingNote+' '+text.xlsxTerms]];
sheet.getRange(`A${last+2}:K${last+2}`).format.wrapText=true;sheet.getRange(`A${last+2}:K${last+2}`).format.rowHeight=48;
const guide=wb.worksheets.add(text.guideSheet);
const guidePath=fileURLToPath(new URL('../assets/guides/'+(zh?'size-guide-cn.jpeg':'size-guide-en.jpeg'),import.meta.url));
guide.images.add({dataUrl:'data:image/jpeg;base64,'+(await fs.readFile(guidePath)).toString('base64'),anchor:{from:{row:0,col:0},extent:{widthPx:670,heightPx:893}}});
wb.recalculate();
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(output);
if(process.env.PETCIRCLE_EXPORT_PREVIEW){const p=await wb.render({sheetName:sheet.name,range:'A1:K9',scale:1,format:'png'});await fs.writeFile(process.env.PETCIRCLE_EXPORT_PREVIEW,new Uint8Array(await p.arrayBuffer()));}
