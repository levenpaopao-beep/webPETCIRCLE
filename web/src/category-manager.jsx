import React,{useEffect,useState} from 'react';
import {ArrowUp,ArrowDown} from '@phosphor-icons/react';
import {api} from './lib';

const label=(cats,id)=>{const c=cats.find(x=>x.id===id);return c?(c.parentId?`${cats.find(x=>x.id===c.parentId)?.zh} › `:'')+c.zh:'未分类'};
const ordered=cats=>cats.filter(c=>!c.parentId).flatMap(c=>[c,...cats.filter(x=>x.parentId===c.id)]);
export function CategoryManager({notify,updated}){
 const [cats,setCats]=useState([]),[base,setBase]=useState([]),[view,setView]=useState('settings'),[folded,setFolded]=useState([]),[dirty,setDirty]=useState(false);
 const [selected,setSelected]=useState(''),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[scope,setScope]=useState('all'),[page,setPage]=useState(1);
 const [data,setData]=useState({products:[],pages:1,total:0}),[chosen,setChosen]=useState([]),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[revision,setRevision]=useState(0),[batch,setBatch]=useState('');
 const load=()=>api('/categories').then(d=>{setCats(d.categories);setBase(d.categories.map(c=>c.id));setDirty(false)});
 useEffect(()=>{load().catch(notify)},[]);
 useEffect(()=>{
  if(view!=='products')return;
  let active=true;setLoading(true);setChosen([]);
  api('/products?'+new URLSearchParams({admin:1,page,search:query,...(selected?{directCategory:selected}:{}),...(scope==='unclassified'?{unclassified:1}:{})}))
   .then(d=>{if(active){setData(d);if(page>d.pages)setPage(d.pages)}}).catch(e=>{if(active)notify(e)}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[view,selected,scope,query,page,revision]);
 const change=(id,values)=>{setCats(old=>old.map(c=>c.id===id?{...c,...values}:c));setDirty(true)};
 const add=parentId=>{setCats(old=>ordered([...old,{id:crypto.randomUUID(),zh:'',en:'',parentId}]));setFolded(old=>old.filter(id=>id!==parentId));setDirty(true)};
 const move=(c,delta)=>{
  const siblings=cats.filter(x=>(x.parentId||'')===(c.parentId||''));const i=siblings.findIndex(x=>x.id===c.id),target=siblings[i+delta];if(!target)return;
  const copy=[...cats],a=copy.findIndex(x=>x.id===c.id),b=copy.findIndex(x=>x.id===target.id);[copy[a],copy[b]]=[copy[b],copy[a]];setCats(ordered(copy));setDirty(true);
 };
 const remove=c=>{
  if(cats.some(x=>x.parentId===c.id)){notify('请先调整或移除所属子分类');return}
  if(window.confirm(`移除“${c.zh||'新分类'}”？产品的其他分类及上下架状态保留。`)){setCats(old=>old.filter(x=>x.id!==c.id));setDirty(true)}
 };
 const save=async()=>{setBusy(true);try{
  await api('/admin/categories',{categories:ordered(cats),replace:true,baseIds:base});await load();updated();window.dispatchEvent(new Event('petcircle-categories-updated'));notify('分类设置已保存');
 }catch(e){notify(e)}finally{setBusy(false)}};
 const switchView=next=>{if(next==='products'&&dirty){notify('请先保存分类设置，再进行产品归类');return}setView(next)};
 const assign=async(mode,codes,id)=>{if(!id)return;setBusy(true);try{
  await api('/admin/products',{codes,changes:{categoryIds:[id],categoryMode:mode}});setChosen([]);setRevision(x=>x+1);updated();window.dispatchEvent(new Event('petcircle-categories-updated'));notify('产品归类已保存');
 }catch(e){notify(e)}finally{setBusy(false)}};
 const showProducts=id=>{if(dirty){notify('请先保存分类设置，再查看产品');return}setSelected(id);setScope('all');setPage(1);setView('products')};
 return <div className="compact-categories">
  <div className="classification-tabs" role="tablist" aria-label="分类管理"><button role="tab" aria-selected={view==='settings'} onClick={()=>switchView('settings')}>分类设置</button><button role="tab" aria-selected={view==='products'} onClick={()=>switchView('products')}>产品归类</button></div>
  {view==='settings'?<section aria-label="分类设置">
   <div className="classification-toolbar"><button className="btn secondary small" disabled={busy} onClick={()=>add('')}>添加主分类</button><button className="btn small" disabled={busy||!dirty} onClick={save}>{busy?'正在保存…':'保存设置'}</button></div>
   <div className="table-scroll"><table className="classification-settings"><thead><tr><th>中文分类名</th><th>英文分类名</th><th>所属主分类</th><th>排序</th><th>分类产品</th><th>操作</th></tr></thead><tbody>{ordered(cats).filter(c=>!c.parentId||!folded.includes(c.parentId)).map(c=>{
    const siblings=cats.filter(x=>(x.parentId||'')===(c.parentId||'')),index=siblings.findIndex(x=>x.id===c.id),children=cats.some(x=>x.parentId===c.id);
    return <tr key={c.id} className={c.parentId?'classification-child':''}><td><div className="classification-name">{!c.parentId?<button className="classification-fold" disabled={!children} aria-label={(folded.includes(c.id)?'展开':'收起')+' '+(c.zh||'分类')} aria-expanded={!folded.includes(c.id)} onClick={()=>setFolded(old=>old.includes(c.id)?old.filter(x=>x!==c.id):[...old,c.id])}>{children?(folded.includes(c.id)?'+':'−'):'·'}</button>:<span className="classification-branch" aria-hidden="true">└</span>}<input aria-label={'中文分类名 '+(c.zh||'新分类')} value={c.zh} disabled={busy} onChange={e=>change(c.id,{zh:e.target.value})}/></div></td><td><input aria-label={'英文分类名 '+(c.zh||'新分类')} value={c.en} disabled={busy} onChange={e=>change(c.id,{en:e.target.value})}/></td><td><select aria-label={'所属主分类 '+(c.zh||'新分类')} value={c.parentId||''} disabled={busy||children} onChange={e=>change(c.id,{parentId:e.target.value})}><option value="">主分类</option>{cats.filter(x=>!x.parentId&&x.id!==c.id).map(x=><option key={x.id} value={x.id}>{x.zh||'未命名主分类'}</option>)}</select></td><td><div className="classification-inline"><button disabled={busy||index===0} aria-label={'上移 '+c.zh} onClick={()=>move(c,-1)}><ArrowUp size={16}/></button><button disabled={busy||index===siblings.length-1} aria-label={'下移 '+c.zh} onClick={()=>move(c,1)}><ArrowDown size={16}/></button></div></td><td><button className="text-link" disabled={busy||!base.includes(c.id)} onClick={()=>showProducts(c.id)}>产品列表</button></td><td><div className="classification-inline">{!c.parentId&&<button className="text-link" disabled={busy} onClick={()=>add(c.id)}>＋子分类</button>}<button className="text-link" disabled={busy} onClick={()=>remove(c)}>移除</button></div></td></tr>
   })}</tbody></table></div>
  </section>:<section aria-label="产品归类">
   <div className="classification-toolbar"><select aria-label="筛选产品分类" value={selected} disabled={busy} onChange={e=>{setSelected(e.target.value);setPage(1);setScope('all')}}><option value="">全部分类</option>{ordered(cats).map(c=><option key={c.id} value={c.id}>{label(cats,c.id)}</option>)}</select><form className="search" onSubmit={e=>{e.preventDefault();setQuery(search);setPage(1)}}><input aria-label="搜索归类产品" placeholder="款号、中文或英文名称" value={search} onChange={e=>setSearch(e.target.value)}/><button>搜索</button></form><div className="classification-scope"><button aria-pressed={scope==='all'} onClick={()=>{setScope('all');setPage(1)}}>全部产品</button><button aria-pressed={scope==='unclassified'} onClick={()=>{setScope('unclassified');setSelected('');setPage(1)}}>未分类产品</button></div></div>
   <div className="classification-toolbar classification-batch"><span>{loading?'正在读取…':`共 ${data.total} 款 · 已选 ${chosen.length} 款`}</span><select aria-label="批量操作分类" value={batch} onChange={e=>setBatch(e.target.value)}><option value="">选择分类</option>{ordered(cats).map(c=><option key={c.id} value={c.id}>{label(cats,c.id)}</option>)}</select><button disabled={busy||loading||!chosen.length||!batch} onClick={()=>assign('add',chosen,batch)}>批量添加</button><button disabled={busy||loading||!chosen.length||!batch} onClick={()=>assign('remove',chosen,batch)}>批量移出</button></div>
   <div className="table-scroll"><table className="classification-products"><thead><tr><th><input type="checkbox" aria-label="选择本页产品" disabled={busy||loading} checked={data.products.length>0&&chosen.length===data.products.length} onChange={e=>setChosen(e.target.checked?data.products.map(p=>p.code):[])}/></th><th>产品信息</th><th>所属分类</th><th>操作</th></tr></thead><tbody>{!loading&&data.products.map(p=><tr key={p.code}><td><input type="checkbox" aria-label={'选择 '+p.code} disabled={busy} checked={chosen.includes(p.code)} onChange={e=>setChosen(e.target.checked?[...chosen,p.code]:chosen.filter(x=>x!==p.code))}/></td><td><div className="table-product">{p.image&&<img src={p.image} alt=""/>}<div>{p.nameZh}<small>{p.code}</small></div></div></td><td><div className="classification-tags">{p.categoryIds.length?p.categoryIds.map(id=><span key={id}>{label(cats,id)}<button disabled={busy} aria-label={'将 '+p.code+' 移出 '+label(cats,id)} onClick={()=>assign('remove',[p.code],id)}>×</button></span>):'未分类'}</div></td><td><select aria-label={'添加 '+p.code+' 到分类'} value="" disabled={busy} onChange={e=>assign('add',[p.code],e.target.value)}><option value="">添加到分类…</option>{ordered(cats).filter(c=>!p.categoryIds.includes(c.id)).map(c=><option key={c.id} value={c.id}>{label(cats,c.id)}</option>)}</select></td></tr>)}</tbody></table></div>
   {!loading&&!data.products.length&&<p className="subtle">暂无产品</p>}<div className="pagination"><button disabled={loading||busy||page<=1} onClick={()=>setPage(page-1)}>上一页</button><span>{page} / {data.pages}</span><button disabled={loading||busy||page>=data.pages} onClick={()=>setPage(page+1)}>下一页</button></div>
  </section>}
 </div>;
}
