'use strict';
(function(){
const DS='LAMAH_CE_PUBLIC_V1';
const state={dataset:DS,station:DS+':2',kind:'TEMPORAL_HOLDOUT',model:'P2-L1',tab:'station',display:'raw',mapmode:'nse',date:'2016-01',report:'p4_report'};
let catalog=null,ticket=0;window.WEBR1={state:state,ready:false,last:null};
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=3)=>v===null||v===undefined||v===''?'N/A':Number.isFinite(Number(v))?Number(v).toFixed(d):'N/A';
const tag=(s,style)=>'<span class="tag '+(style||'')+'">'+esc(s)+'</span>';
const params=o=>new URLSearchParams(o).toString();
function scope(extra,kind){kind=kind||state.kind;return Object.assign({dataset:state.dataset,kind:kind,snapshot:catalog.releases[kind].source_snapshot_id,model:state.model},extra||{});}
async function api(route,q){let r=await fetch('/api/public/'+route+(q?'?'+params(q):''));let body=await r.json();if(!r.ok){let e=new Error(body.status);e.body=body;throw e;}return body;}
function table(headers,rows){return '<div class="tablewrap"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
function station(g){return catalog.stations.find(r=>r.gauge_id===Number(g));}
function metric(v){return '<span class="'+(v===null?'na':v<0?'negative':'')+'">'+fmt(v)+'</span>';}
function chart(rows){
if(!rows.length)return '<div class="empty">此站没有该类别的封存预测。NO_RESULTS_FOR_SELECTION</div>';
const W=850,H=320,L=62,R=20,T=20,B=45;
let values=rows.flatMap(r=>[r.qsim_raw,r.interval_90_lower,r.interval_90_upper]).filter(v=>v!==null);
const lo=Math.min(0,...values),hi=Math.max(...values),span=hi-lo||1;
const x=i=>L+i*(W-L-R)/Math.max(1,rows.length-1),y=v=>T+(hi-v)*(H-T-B)/span;
let s='<svg class="chart" viewBox="0 0 '+W+' '+H+'" aria-label="封存Qsim与90%经验区间；不含Qobs" role="img">';
for(let i=0;i<=4;i++){let v=lo+span*i/4;s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y(v)+'" y2="'+y(v)+'" stroke="#e9eff4"/><text x="'+(L-10)+'" y="'+(y(v)+4)+'" text-anchor="end">'+fmt(v,1)+'</text>';}
if(rows.every(r=>r.interval_90_lower!==null&&r.interval_90_upper!==null)){
let p=rows.map((r,i)=>x(i)+','+y(r.interval_90_upper)).concat(rows.map((r,i)=>x(i)+','+y(r.interval_90_lower)).reverse()).join(' ');
s+='<polygon points="'+p+'" fill="#d4e5ed" opacity=".75"/>';}
const key=state.display==='raw'?'qsim_raw':'qsim_nonnegative';
s+='<polyline points="'+rows.map((r,i)=>x(i)+','+y(r[key])).join(' ')+'" fill="none" stroke="#247a9e" stroke-width="2.4"/>';
rows.forEach((r,i)=>{s+='<circle cx="'+x(i)+'" cy="'+y(r[key])+'" r="2.8" fill="#247a9e"><title>'+r.year+'-'+String(r.month).padStart(2,'0')+' Qsim='+r[key]+'</title></circle>';if(i===0||i===rows.length-1||i%Math.max(1,Math.floor(rows.length/5))===0)s+='<text x="'+x(i)+'" y="'+(H-20)+'" text-anchor="middle">'+r.year+'-'+String(r.month).padStart(2,'0')+'</text>';});
return s+'<text x="12" y="13">m³/s</text></svg><div class="legend"><span><i></i>Qsim '+(state.display==='raw'?'原始预测':'非负次分析')+'</span><span><i class="band"></i>原始预测的90%经验区间</span><span>缺失保留为空 · Qobs不导出</span></div>';
}
function reportButtons(){return catalog.reports.map(r=>'<button class="btn reportbtn" data-report="'+esc(r.id)+'">'+({p4_report:'P4科研报告',p5_report:'P5稳健性报告',model_card:'模型卡',license:'许可与署名'}[r.id])+'</button>').join('');}
async function render(){
const t=++ticket;window.WEBR1.ready=false;window.WEBR1.last=null;$('#view').innerHTML='<div class="card muted">读取所选快照…</div>';
$('.controls').style.display=state.dataset===DS?'grid':'none';$('#counts').style.display=state.dataset===DS?'grid':'none';
document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===state.tab));
if(state.dataset!==DS){
$('#view').innerHTML='<div class="error"><h2>'+esc(state.dataset==='SYRDARYA'?'MODEL_EXECUTION_NOT_AUTHORIZED':'SOURCE_DATA_MISMATCH')+'</h2><p>'+esc(state.dataset==='SYRDARYA'?'教师数据权限保持不变；本预览不读取其Q，也不展示公开流域缓存。':'原网站OPEN_METADATA_ONLY快照与独立公开科研快照不同，不能仅凭LAMAHCE名称合并。')+'</p><p>此页已清除上一数据集预测、评价与地图。</p></div>';
window.WEBR1.ready=true;return;}
let html='';
try{
if(state.tab==='station'||state.tab==='overview'){
let d=await api('results',scope({station:state.station}));let e=await api('evaluation',scope({station:state.station},'TEMPORAL_HOLDOUT'));if(t!==ticket)return;
window.WEBR1.last=d;
let rows=d.records,st=catalog.stations.find(r=>r.station_uid===state.station),m=e.records[0],first=rows[0];
html='<div class="twocol"><section class="card"><div class="cardhead"><div><h2>ID'+st.gauge_id+' · '+esc(st.name)+'</h2><div class="muted">'+esc(st.river)+' · 月平均径流 · m³/s</div></div>'+tag(d.status,rows.length?'':'gray')+'</div><p>'+tag(state.kind,state.kind==='FINAL_MODEL_APPLICATION'?'amber':'')+'</p>'+chart(rows)+'<div class="hashnote muted">'+(state.kind==='FINAL_MODEL_APPLICATION'?'最终V2应用：2016已参与训练，不是新的独立评价。':state.kind==='MASKED_GAP_EVALUATION'?'真实排除2016目标Q的人工连续缺档评价，不是真正历史缺档。':'V1：截至2014训练，对2015–2017时间外评分。')+'</div></section><section class="card"><h3>V1独立评价 · '+esc(state.model)+'</h3>'+(m?'<div class="metricrow"><div><b>'+metric(m.NSE)+'</b><span>NSE</span></div><div><b>'+metric(m.KGE)+'</b><span>KGE</span></div><div><b>'+m.n_months+'</b><span>合法月</span></div></div>':tag('NOT_EVALUATED','gray')+'<p class="muted">NO_ELIGIBLE_TEST_SUPPORT</p>')+'<p class="muted">以上为原V1模型的独立评分；不代表V2的新测试成绩。</p><dl><dt>当前预测模型训练截止</dt><dd>'+esc(first?first.training_cutoff:'无此类别模型')+'</dd><dt>所选来源快照</dt><dd class="mono">'+esc(d.scope.source_snapshot_id)+'</dd><dt>所选模型发布</dt><dd class="mono">'+esc(d.scope.model_release_id)+'</dd><dt>模型哈希</dt><dd class="mono">'+esc(first?first.model_hash:'N/A')+'</dd></dl>'+tag('REACH_PREDICTION_NOT_AVAILABLE','gray')+'</section></div>';
if(m){html+='<section class="card"><h3>V1经验区间诊断 · 同一评价快照</h3>'+table(['名义覆盖','实际覆盖','平均区间宽度 m³/s','合法月'],e.coverage.map(r=>[fmt(r.nominal*100,0)+'%',fmt(r.coverage*100,2)+'%',fmt(r.mean_width),r.n]))+'<p class="muted">覆盖偏高不代表精度认证；经验区间无严格无条件覆盖保证。</p></section>';
html+='<section class="card"><h3>逐年评分 · 原始预测</h3>'+table(['年份','合法月','NSE','KGE','RMSE','MAE','PBIAS %'],e.yearly.map(r=>[r.year,r.n_months,metric(r.NSE),metric(r.KGE),fmt(r.RMSE),fmt(r.MAE),fmt(r.PBIAS,2)]))+'</section>';}
}else if(state.tab==='evaluation'){
let out=await Promise.all(['C0+PT','P2-L1'].map(model=>api('evaluation',scope({model:model},'TEMPORAL_HOLDOUT'))));if(t!==ticket)return;
const base=new Map(out[0].records.map(r=>[r.gauge_id,r]));const current=state.model==='P2-L1'?out[1]:out[0];
html='<section class="card"><div class="cardhead"><div><h2>25站独立时间外评价</h2><div class="muted">V1 · 2015–2017 · 899站月 · 原始预测主分析</div></div>'+tag('TEMPORAL_HOLDOUT')+'</div><p class="muted">611、688没有合法测试支持，保留N/A。负NSE原样展示，不以0替代。</p>'+table(['站点','C0+PT NSE','P2-L1 NSE',state.model+' KGE','RMSE','MAE','PBIAS %','月数','状态'],out[1].records.map(l=>{let a=base.get(l.gauge_id),r=current.records.find(v=>v.gauge_id===l.gauge_id);return ['<button class="linkstation" data-station="'+l.gauge_id+'">ID'+l.gauge_id+'</button>',metric(a.NSE),metric(l.NSE),metric(r.KGE),fmt(r.RMSE),fmt(r.MAE),fmt(r.PBIAS,2),r.n_months==null?'N/A':r.n_months,tag(r.evaluation_status,r.evaluation_status==='NOT_EVALUATED'?'gray':r.NSE<0?'red':'')];}))+'</section>';
}else if(state.tab==='spatial'){
let d=await api('spatial',scope({date:state.date}));if(t!==ticket)return;window.WEBR1.last=d;
let vals=d.features.map(f=>f.properties.coordinates_epsg3035),xs=vals.map(p=>p[0]),ys=vals.map(p=>p[1]),xmin=Math.min(...xs)-30000,xmax=Math.max(...xs)+30000,ymin=Math.min(...ys)-30000,ymax=Math.max(...ys)+30000;
let x=v=>40+(v-xmin)*820/(xmax-xmin),y=v=>480-(v-ymin)*420/(ymax-ymin),svg='<svg class="chart" viewBox="0 0 900 520" role="img" aria-label="EPSG3035站点结果，不含河段预测"><rect x="35" y="30" width="840" height="455" fill="#f3f7fa"/>';
for(let i=0;i<=4;i++){let vx=xmin+(xmax-xmin)*i/4,vy=ymin+(ymax-ymin)*i/4;svg+='<line x1="'+x(vx)+'" x2="'+x(vx)+'" y1="30" y2="485" stroke="#e0e9ef"/><line x1="35" x2="875" y1="'+y(vy)+'" y2="'+y(vy)+'" stroke="#e0e9ef"/><text x="'+x(vx)+'" y="506" text-anchor="middle">'+Math.round(vx/1000)+' km</text><text x="8" y="'+y(vy)+'">'+Math.round(vy/1000)+'</text>';}
d.features.forEach(f=>{let p=f.properties,cov=p.uncertainty.find(v=>v.model_id===state.model&&v.nominal===.9),v=state.mapmode==='nse'?p.NSE:state.mapmode==='qsim'?p.qsim:state.mapmode==='coverage'?cov?cov.coverage:null:state.mapmode==='width'?cov?cov.mean_width:null:p.model_count;
let color=v===null?'#a8b4bf':state.mapmode==='nse'?(v<0?'#bd685c':'#368c9e'):'#37849d',r=state.mapmode==='qsim'&&v!==null?Math.min(18,5+Math.sqrt(Math.max(0,v))):8;
svg+='<circle class="mapdot '+(p.station_uid===state.station?'selected':'')+'" data-gauge="'+p.gauge_id+'" cx="'+x(p.coordinates_epsg3035[0])+'" cy="'+y(p.coordinates_epsg3035[1])+'" r="'+r+'" fill="'+color+'"><title>ID'+p.gauge_id+' '+esc(p.name)+' '+state.mapmode+'='+fmt(v)+'</title></circle><text class="maplabel" x="'+(x(p.coordinates_epsg3035[0])+10)+'" y="'+(y(p.coordinates_epsg3035[1])-9)+'">'+p.gauge_id+'</text>';});
svg+='</svg>';
html='<section class="card"><div class="cardhead"><div><h2>站点空间结果 · EPSG:3035</h2><div class="muted">27个真实站点点位；误差/区间来自V1快照，Qsim来自当前选择的封存成果。</div></div>'+tag('POINT LAYERS ONLY')+'</div><div class="rowflex"><label>图层<select id="mapmode"><option value="nse">V1 独立误差 · NSE</option><option value="qsim">所选时间 · 站点Qsim</option><option value="coverage">V1 90%区间实际覆盖</option><option value="width">V1 90%区间平均宽度</option><option value="applicability">已保存模型适用状态</option></select></label><label>Qsim月份<input id="mapdate" type="month" value="'+state.date+'"></label><span class="muted">蓝=有值 / 红=NSE负 / 灰=无合法结果</span></div><div class="mapwrap">'+svg+'</div><div class="statuslist">'+Object.values(d.layers).map(r=>tag(r.status,r.status==='REACH_PREDICTION_NOT_AVAILABLE'?'gray':'')).join('')+'</div><p class="muted">reach_id=null；无经认证的河段映射，不将站点Qsim扩散至河网。</p></section>';
let p=d.features.find(f=>f.properties.station_uid===state.station).properties;html+='<section class="card"><h3>ID'+p.gauge_id+' · '+esc(p.name)+'</h3><div class="rowflex"><span>V1 NSE '+metric(p.NSE)+'</span><span>所选Qsim '+fmt(p.qsim)+' m³/s</span>'+tag(p.input_support_status||'NO_RESULTS_FOR_SELECTION','gray')+'</div><div class="mono">Qsim snapshot: '+esc(p.qsim_source_snapshot_id)+'<br>Evaluation snapshot: '+esc(p.evaluation_source_snapshot_id)+'</div></section>';
}else if(state.tab==='report'){
let r=await api('report',{dataset:DS,id:state.report});if(t!==ticket)return;
html='<section class="card"><h2>科研报告、模型卡与许可</h2>'+reportButtons()+'<div class="mono">SHA256 '+r.sha256+'</div><pre class="reporttext">'+esc(r.content)+'</pre></section>';
}else if(state.tab==='models'){
html='<section class="card"><h2>27站 · 54个正式保存模型</h2><p class="muted">默认研究公式P2-L1；C0+PT为强制基线。P5-SHRINK仅内部探索，不注册为发布模型。</p><button class="btn" id="execute">验证网页执行门禁（预期403）</button><span id="executionResult"></span>'+table(['站点','模型','版本','截止','模型哈希'],catalog.models.map(r=>['ID'+r.gauge_id,esc(r.model_id),'P4-V2',r.training_cutoff,'<span class="mono">'+r.model_hash.slice(0,20)+'…</span>']))+'</section>';
}else{
html='<section class="card"><h2>分离的数据来源与权限</h2>'+table(['来源','身份','用途','状态'],[['V1时间外测试','27模型站 / 25合法评分站','2015–2017独立评分',tag('TEMPORAL_HOLDOUT')],['V2应用','648条 / 2016年','最终保存模型推理',tag('FINAL_MODEL_APPLICATION','amber')],['人工遮蔽','ID2 / 24条','排除2016Q的模型','MASKED_GAP_EVALUATION'],['真实缺档','0条','未发现合格全缺测月','NO_ELIGIBLE_TRUE_GAPS'],['旧LAMAHCE快照','OPEN_METADATA_ONLY','旧网站元数据','不与公开快照混合'],['Syr Darya','教师数据受限','本预览不读取','403保持']])+'</section>';
}
if(t!==ticket)return;$('#view').innerHTML=html;window.WEBR1.ready=true;
document.querySelectorAll('[data-station]').forEach(b=>b.onclick=()=>{state.station=DS+':'+b.dataset.station;state.tab='station';sync();render();});
document.querySelectorAll('[data-gauge]').forEach(b=>b.onclick=()=>{state.station=DS+':'+b.dataset.gauge;sync();render();});
document.querySelectorAll('[data-report]').forEach(b=>b.onclick=()=>{state.report=b.dataset.report;render();});
if($('#mapmode')){$('#mapmode').value=state.mapmode;$('#mapmode').onchange=e=>{state.mapmode=e.target.value;render();};$('#mapdate').onchange=e=>{state.date=e.target.value;render();};}
if($('#execute'))$('#execute').onclick=async()=>{let r=await fetch('/api/v6/model/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset:state.dataset})});let d=await r.json();$('#executionResult').textContent=r.status+' '+d.status;};
}catch(e){if(t!==ticket)return;$('#view').innerHTML='<div class="error"><h2>'+esc(e.message)+'</h2><p>失败保留为错误状态，不以0填充。</p></div>';window.WEBR1.ready=true;window.WEBR1.error=e.message;}
}
function sync(){for(const k of ['dataset','station','kind','model','display'])$('#'+k).value=state[k];}
async function init(){
catalog=await api('catalog');window.WEBR1.catalog=catalog;
$('#station').innerHTML=catalog.stations.map(s=>'<option value="'+s.station_uid+'">ID'+s.gauge_id+' · '+esc(s.name)+'</option>').join('');
$('#counts').innerHTML=[['54','可加载模型','27站 × 2固定公式'],['25','独立评价站','V1 · 2015–2017'],['899','合法测试站月','两个模型共1798条预测'],['0','真实缺档重建','NO_ELIGIBLE_TRUE_GAPS']].map(r=>'<div class="kpi"><b>'+r[0]+'</b><span>'+r[1]+'</span><small>'+r[2]+'</small></div>').join('');
let h=new URLSearchParams(location.hash.includes('?')?location.hash.split('?')[1]:'');for(const k of ['dataset','station','kind','model','tab'])if(h.has(k))state[k]=h.get(k);
sync();for(const k of ['dataset','station','kind','model','display'])$('#'+k).onchange=e=>{state[k]=e.target.value;render();};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{state.tab=b.dataset.tab;render();});render();
}
init().catch(e=>{$('#view').textContent='SOURCE_DATA_MISMATCH / '+e.message;});
})();