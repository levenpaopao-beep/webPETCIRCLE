"""从已经锁定的报价快照生成对客文件，不重新计算历史价格。"""
import io,json,os,subprocess,tempfile
from server.languages import normalize_language, document_messages
from pathlib import Path
from xml.sax.saxutils import escape

def export_quote(q,kind,state):
    if kind=='xlsx':
        from server.app import EXPORT_NODE
        with tempfile.TemporaryDirectory(dir=state) as tmp:
            p=Path(tmp);(p/'input.json').write_text(json.dumps({'quote':q,'imageRoot':str(state/'quote-images')},ensure_ascii=False))
            env=os.environ.copy()
            result=subprocess.run([str(EXPORT_NODE),str(Path(__file__).with_name('export-xlsx.mjs')),str(p/'input.json'),str(p/'quote.xlsx')],capture_output=True,timeout=120,env=env)
            if result.returncode:raise RuntimeError(result.stderr.decode()[-2000:])
            return (p/'quote.xlsx').read_bytes(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer,Image,PageBreak
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font='/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
    if not pdfmetrics.getRegisteredFontNames().__contains__('SiteUnicode'):pdfmetrics.registerFont(TTFont('SiteUnicode',font))
    style=ParagraphStyle('body',fontName='SiteUnicode',fontSize=8,leading=12)
    title=ParagraphStyle('title',fontName='SiteUnicode',fontSize=20,leading=26,textColor=colors.HexColor('#142D42'))
    P=lambda s:Paragraph(escape(str(s)),style)
    language=normalize_language(q.get('language'));text=document_messages(language);zh=language=='zh';out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=30,rightMargin=30,topMargin=30,bottomMargin=30)
    story=[Paragraph('PETCIRCLE | '+text['title'],title),Spacer(1,10),P(q.get('companyZh',q['company']) if zh else q['company']),P(q['number']+' · '+q['createdAt'][:10]+' · '+q['currency']),P(q['buyer']['company']+' | '+q['buyer']['contact']+' | '+q['buyer']['email']),P('levenwong@foxmail.com | WhatsApp +852 8483 1068 | '+text['wechat']+': levenwong'),Spacer(1,14)]
    heads=text['pdfHeads']
    data=[[P(x) for x in heads]]
    for l in q['lines']:
        image=Image(str(state/'quote-images'/l['image']),width=74,height=74,kind='proportional')
        pack=(str(l['cartonQty'])+' '+text['pieces']+' / '+l['cartonSize']) if l['cartonQty'] and l['cartonSize'] else text['pending']
        if l['unitWeightG']:pack+=' / '+str(l['unitWeightG'])+' '+text['grams']
        data.append([image,P(l['code']+'\n'+(l['nameZh'] if zh else l['nameEn'])),P((l['color'] if zh else l['colorEn'])+' / '+(('均码' if zh else 'One size') if str(l['size']).lower().replace(' ','') in ['均码','onesize'] else l['size'])),P(l['quantity']),P(f"{l['unitPrice']:.2f}"),P(f"{l['amount']:.2f}"),P(pack)])
    table=Table(data,colWidths=[88,190,110,42,65,75,210-68],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8ECEE')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#DDE2E5')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story += [table,Spacer(1,12),P(text['quantity']+': '+str(q['quantity'])+' | '+text['total']+': '+q['currency']+f" {q['total']:.2f}"),Spacer(1,8),P(q['packingNote']),P(text['terms'])]
    guide=Path(__file__).resolve().parents[1]/'assets/guides'/('size-guide-cn.jpeg' if zh else 'size-guide-en.jpeg')
    story += [PageBreak(),Image(str(guide),width=360,height=480,kind='proportional')]
    def footer(canvas,doc):
        canvas.setFont('SiteUnicode',8);canvas.setFillColor(colors.HexColor('#60717C'));canvas.drawString(30,18,q['number']);canvas.drawRightString(812,18,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue(),'application/pdf'
