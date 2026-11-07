/* R2U1: public results are views of the original VHS router, state, cards and API client. */
(function(){
'use strict';var V=window.VHS,DS='LAMAH_CE_PUBLIC_V1';
var base='/api/v6/candidate-public/',original={};Object.keys(V.views).forEach(function(k){original[k]=V.views[k];});
function n(x,d){return x===null||x===undefined||!Number.isFinite(Number(x))?'N/A':Number(x).toFixed(d===undefined?3:d);}
function val(x){return {html:'<span class="'+(x!==null&&x<0?'negative':'')+'">'+n(x)+'</span>'};}
function get(path,q){return V.get(base+path+(q?'?'+new URLSearchParams(q).toString():''));}
function scope(cat,extra,kind){kind=kind||V.state.publicKind;return Object.assign({dataset:DS,kind:kind,snapshot:cat.releases[kind].source_snapshot_id,model:V.state.publicModel},extra||{});}
function controls(cat){
 var st=V.state.station||DS+':2';
 return '<div class="r2-controls"><label>测站'+V.select('r2Station',cat.stations.map(function(r){return {value:r.station_uid,label:'ID'+r.gauge_id+' · '+r.name};}),st)+'</label>'+
 '<label>封存成果'+V.select('r2Kind',[{value:'TEMPORAL_HOLDOUT',label:'V1 · 2015–2017时间外评价'},{value:'FINAL_MODEL_APPLICATION',label:'V2 · 最终模型应用（非OOF）'},{value:'MASKED_GAP_EVALUATION',label:'ID2 · 人工连续遮蔽'}],V.state.publicKind)+'</label>'+
 '<label>模型'+V.select('r2Model',['P2-L1','C0+PT'],V.state.publicModel)+'</label>'+
 '<label>开始月<input type="month" id="r2Start" value="'+V.e(V.state.publicStart)+'"></label>'+
 '<label>结束月<input type="month" id="r2End" value="'+V.e(V.state.publicEnd)+'"></label></div>';
}
function mount(root,ctx){
 V.onChange(root,'r2Station',function(s){V.go(ctx.layer,ctx.sub,{station:s});});
 V.onChange(root,'r2Model',function(m){V.go(ctx.layer,ctx.sub,{model:m});});
 V.onChange(root,'r2Kind',function(k){V.go(ctx.layer,ctx.sub,{kind:k,start:k==='TEMPORAL_HOLDOUT'?'2015-01':'2016-01',end:k==='TEMPORAL_HOLDOUT'?'2017-12':'2016-12'});});
 ['Start','End'].forEach(function(s){V.onChange(root,'r2'+s,function(x){var p={};p[s.toLowerCase()]=x;V.go(ctx.layer,ctx.sub,p);});});
 V.onChange(root,'r2MapMode',function(m){V.go(ctx.layer,ctx.sub,{mapmode:m});});
 root.querySelectorAll('[data-r2-station]').forEach(function(b){b.onclick=function(){V.go('results',null,{station:b.dataset.r2Station,model:b.dataset.r2Model||V.state.publicModel});};});
 root.querySelectorAll('[data-r2-mapstation]').forEach(function(b){b.onclick=function(){V.go(ctx.layer,ctx.sub,{station:b.dataset.r2Mapstation});};});
 root.querySelectorAll('[data-r2-report]').forEach(function(b){b.onclick=function(){V.go('results','report',{report:b.dataset.r2Report});};});
 var ex=root.querySelector('#r2Execute');if(ex)ex.onclick=async function(){try{await V.api('/api/v6/model/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset:DS})});}catch(e){root.querySelector('#r2ExecResult').textContent=e.status+' '+((e.body||{}).status||'NOT_AUTHORIZED');}};
}
function chart(rows){
 if(!rows.length)return V.empty('NO_RESULTS_FOR_SELECTION：无此站/类别/年月的封存预测，不补零。');
 var w=1000,h=330,L=60,R=22,T=24,B=40,values=[];rows.forEach(function(r){[r.qsim_raw,r.interval_90_lower,r.interval_90_upper].forEach(function(x){if(x!==null)values.push(x);});});
 var low=Math.min(0,...values),high=Math.max(...values),span=high-low||1;function X(i){return L+(w-L-R)*i/Math.max(1,rows.length-1);}function Y(y){return T+(high-y)*(h-T-B)/span;}
 var s='<div class="chart"><svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="真实封存预测与区间，无Qobs">';
 for(var j=0;j<=4;j++){var y=low+span*j/4;s+='<line x1="'+L+'" x2="'+(w-R)+'" y1="'+Y(y)+'" y2="'+Y(y)+'" stroke="#e1e9ef"/><text x="'+(L-8)+'" y="'+(Y(y)+4)+'" text-anchor="end">'+n(y,1)+'</text>';}
 if(rows.every(function(r){return r.interval_90_lower!==null&&r.interval_90_upper!==null;})){
 var p=rows.map(function(r,i){return X(i)+','+Y(r.interval_90_upper);}).concat(rows.map(function(r,i){return X(i)+','+Y(r.interval_90_lower);}).reverse()).join(' ');s+='<polygon points="'+p+'" fill="#d3e5ef" opacity=".8"/>';}
 s+='<polyline points="'+rows.map(function(r,i){return X(i)+','+Y(r.qsim_raw);}).join(' ')+'" fill="none" stroke="#1f5fa8" stroke-width="2.3"/>';
 rows.forEach(function(r,i){s+='<circle cx="'+X(i)+'" cy="'+Y(r.qsim_raw)+'" r="2.5" fill="#1f5fa8"><title>'+r.year+'-'+r.month+': '+r.qsim_raw+'</title></circle>';if(i===0||i===rows.length-1||i%Math.max(1,Math.floor(rows.length/5))===0)s+='<text x="'+X(i)+'" y="'+(h-14)+'" text-anchor="middle">'+r.year+'-'+String(r.month).padStart(2,'0')+'</text>';});
 return s+'<text x="10" y="14">m³/s</text></svg></div><div class="legend">原始Qsim主分析 · 90%经验区间 · Qobs不导出</div>';
}
function spatialMap(d){
 var pts=d.features.map(function(f){return f.properties.coordinates_epsg3035;}),xs=pts.map(function(p){return p[0];}),ys=pts.map(function(p){return p[1];}),xmin=Math.min(...xs)-30000,xmax=Math.max(...xs)+30000,ymin=Math.min(...ys)-30000,ymax=Math.max(...ys)+30000;
 var scale=Math.min(875/(xmax-xmin),435/(ymax-ymin)),ox=55+(875-(xmax-xmin)*scale)/2,oy=65+(435-(ymax-ymin)*scale)/2;function X(x){return ox+(x-xmin)*scale;}function Y(y){return oy+(ymax-y)*scale;}
 var s='<svg viewBox="0 0 1000 550" role="img" aria-label="EPSG3035站点结果，不是河段预测"><rect x="45" y="35" width="900" height="480" fill="#f3f7fa"/>';
 for(var i=0;i<=4;i++){var xx=xmin+(xmax-xmin)*i/4,yy=ymin+(ymax-ymin)*i/4;s+='<line x1="'+X(xx)+'" x2="'+X(xx)+'" y1="35" y2="515" stroke="#dde6ef"/><line x1="45" x2="945" y1="'+Y(yy)+'" y2="'+Y(yy)+'" stroke="#dde6ef"/><text x="'+X(xx)+'" y="539" text-anchor="middle">'+Math.round(xx/1000)+' km</text><text x="3" y="'+Y(yy)+'">'+Math.round(yy/1000)+'</text>';}
 d.features.forEach(function(f){var p=f.properties,cov=p.uncertainty.find(function(r){return r.model_id===V.state.publicModel&&r.nominal===.9;}),z=V.state.publicMapMode==='nse'?p.NSE:V.state.publicMapMode==='qsim'?p.qsim:V.state.publicMapMode==='coverage'?(cov?cov.coverage:null):V.state.publicMapMode==='width'?(cov?cov.mean_width:null):p.model_count;
 var color=z===null?'#a7b3c0':V.state.publicMapMode==='nse'&&z<0?'#b96459':'#2e879d';
 s+='<circle data-epsg-x="'+p.coordinates_epsg3035[0]+'" data-epsg-y="'+p.coordinates_epsg3035[1]+'" class="r2-mapdot '+(V.state.station===p.station_uid?'selected':'')+'" data-r2-mapstation="'+p.station_uid+'" cx="'+X(p.coordinates_epsg3035[0])+'" cy="'+Y(p.coordinates_epsg3035[1])+'" r="8" fill="'+color+'"><title>ID'+p.gauge_id+' '+V.e(p.name)+' '+n(z)+'</title></circle><text x="'+(X(p.coordinates_epsg3035[0])+9)+'" y="'+(Y(p.coordinates_epsg3035[1])-9)+'">'+p.gauge_id+'</text>';
 });return s+'</svg>';
}
function resultSub(ctx){return V.subnav('results',[{key:'index',label:'站点结果'},{key:'evaluation',label:'模型评估'},{key:'spatial',label:'空间结果'},{key:'report',label:'科研报告'},{key:'research',label:'P6外部验证与解释'},{key:'p7',label:'P7实验候选'}],ctx.sub||'index');}
function decompositionCard(d,selected){
 var ids=new Set(selected.map(function(r){return r.year+'-'+String(r.month).padStart(2,'0');}));
 var rs=d.records.filter(function(r){return r.model_id===V.state.publicModel&&ids.has(r.date);}).sort(function(a,b){return a.date.localeCompare(b.date);});
 if(!rs.length)return V.card({title:'冻结预测分解',body:V.empty('此类别或时间窗没有可核对的分解；不借用其他版本的季节模板。')});
 var v=rs[0].version,c=d.station_summary.find(function(r){return r.version===v&&r.model_id===V.state.publicModel;}),pair=new Map(d.records.filter(function(r){return r.model_id==='C0+PT';}).map(function(r){return [r.date,r];}));
 var all=rs.flatMap(function(r){return [r.seasonal_baseline,r.qsim_frozen];}),lo=Math.min(0,...all),hi=Math.max(...all),span=hi-lo||1,w=1000,h=250;
 function X(i){return 60+900*i/Math.max(1,rs.length-1);}function Y(z){return 20+(hi-z)*185/span;}
 var svg='<svg viewBox="0 0 1000 250" role="img" aria-label="固定十二月季节模板与冻结预测分解">';
 for(var k=0;k<3;k++){var z=lo+span*k/2;svg+='<text x="3" y="'+Y(z)+'">'+n(z,2)+'</text>';}
 [['seasonal_baseline','#a47839'],['qsim_frozen','#1f5fa8']].forEach(function(a){svg+='<polyline fill="none" stroke="'+a[1]+'" stroke-width="2" points="'+rs.map(function(r,i){return X(i)+','+Y(r[a[0]]);}).join(' ')+'"/>';});
 svg+='<text x="12" y="14">m³/s</text><text x="60" y="232">'+rs[0].date+'</text><text x="890" y="232">'+rs[rs.length-1].date+'</text></svg>';
 return V.card({title:'季节模板与气象修正 · '+v,lead:'棕色=训练折十二月Q均值；蓝色=封存预测。模板每年重复；年际差异只能来自气象异常项。不是水文机制因果归因。',body:svg+V.kv([['模板—预测相关（该版本完整封存期）',c?n(c.correlation_prediction_vs_template):'N/A'],['气象修正RMS m³/s（完整封存期）',c?n(c.meteorological_correction_RMS):'N/A'],['108模型alpha',d.summary.alpha_model_count+'个均为100；原网格上边界'],['复算误差',d.summary.max_reproduction_abs_error+'（仅旧预测复算，不fit）']])+V.table(['日期','季节模板','当月P贡献','当月T贡献','直接L1贡献','总气象修正','实际L1−C0PT'],rs.map(function(r){var b=pair.get(r.date);return [r.date,n(r.seasonal_baseline),n(r.P_contribution),n(r.T_contribution),n(r.L1_contribution),n(r.total_meteorological_correction),b&&r.model_id==='P2-L1'?n(r.qsim_frozen-b.qsim_frozen):'N/A'];}))+'<p class="notice">实际L1−C0PT包含直接前月P项及加入L1后P/T系数的重新分配，不能把两者混同。90%经验区间校准每季仅12个残差，使用最大绝对残差并可能乘历史kappa；不保证新时期覆盖。NOT_CERTIFIED。</p>'});
}
async function publicView(ctx){
 var cat=await get('catalog');if(V.state.dataset!==DS)throw new Error('STALE_DATASET_RESPONSE');
 if(!V.state.station)V.state.station=DS+':2';
 var html='<div class="r2-public">'+V.banner('warn','原v0.6主站 · 公开科研候选模块',V.e(cat.notice)+'<br>生产展示尚未批准；当前仅候选本地展示，动态执行仍403。')+V.card({title:'统一公开科研选择',body:controls(cat)});
 var side=V.card({title:'来源与权限',tight:true,body:V.kv([['数据集',DS],['当前测站',V.state.station],['当前模型',V.state.publicModel],['成果类别',V.state.publicKind],['候选展示','本轮用户明确要求的本地测试范围'],['生产展示','NOT_GRANTED'],['动态执行','NOT_AUTHORIZED']])+'<p class="notice">旧LAMAHCE元数据与公开快照独立；不读取教师Q。</p>'});
 var rows,ev,st=cat.stations.find(function(r){return r.station_uid===V.state.station;});
 if(!st)throw new Error('STATION_DATASET_MISMATCH');
 if(ctx.layer==='results'&&(ctx.sub==='evaluation')){
  var pair=await Promise.all(['C0+PT','P2-L1'].map(function(m){return get('results/evaluation',scope(cat,{model:m},'TEMPORAL_HOLDOUT'));}));
  var bm=new Map(pair[0].records.map(function(r){return [r.gauge_id,r];})),selected=V.state.publicModel==='P2-L1'?pair[1]:pair[0];
  html+=resultSub(ctx)+V.card({title:'V1独立时间外评价 · 25站 / 899站月',lead:'2015–2017，原始预测。611/688保留N/A；负NSE不隐藏。V2应用不进入此成绩表。',body:V.table(['站点','C0+PT NSE','P2-L1 NSE',V.state.publicModel+' KGE','RMSE','MAE','PBIAS %','月数','状态'],pair[1].records.map(function(r){var a=bm.get(r.gauge_id),v=selected.records.find(function(z){return z.gauge_id===r.gauge_id;});return [{html:'<button class="btn small" data-r2-station="'+DS+':'+r.gauge_id+'">ID'+r.gauge_id+'</button>'},val(a.NSE),val(r.NSE),val(v.KGE),n(v.RMSE),n(v.MAE),n(v.PBIAS,2),v.n_months===null?'N/A':v.n_months,v.evaluation_status];}))});
 }else if(ctx.layer==='layers'||ctx.layer==='results'&&ctx.sub==='spatial'){
  var map=await get('results/spatial',scope(cat,{date:V.state.publicStart}));
  var cur=map.features.find(function(f){return f.properties.station_uid===V.state.station;}).properties;
  var mode=V.select('r2MapMode',[{value:'nse',label:'V1独立NSE'},{value:'qsim',label:'当前起始月站点Qsim'},{value:'coverage',label:'V1 90%区间覆盖'},{value:'width',label:'V1 90%区间宽度'},{value:'applicability',label:'站点模型适用状态'}],V.state.publicMapMode);
  html+=(ctx.layer==='results'?resultSub(ctx):'')+V.card({title:'站点空间结果 · EPSG:3035',lead:'27站点；误差/区间来自V1，Qsim来自所选类别的起始月。仅站点点结果，绝非河网流量场。',body:'<label>图层 '+mode+'</label>'+spatialMap(map)+'<div class="chips">'+Object.values(map.layers).map(function(r){return V.spill(r.status);}).join(' ')+'</div><p class="notice">红=NSE负；灰=无合法独立评价。reach_id=null，REACH_PREDICTION_NOT_AVAILABLE。</p>'});
  var hist=cur.evaluation[V.state.publicModel]||{},pi=cur.uncertainty.filter(function(r){return r.model_id===V.state.publicModel&&r.nominal===.9;})[0];
  var rs=await get('research-status',scope(cat,{station:V.state.station}));
  side+=V.card({title:'所选空间站点 · 科研状态分离',tight:true,body:V.kv([
   ['站点',cur.name],['V1评价状态',cur.NSE===null?'NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT':'GAUGE_EVALUATION_AVAILABLE'],
   ['V1 NSE / KGE',n(cur.NSE)+' / '+n(hist.KGE)],['V1误差风险',cur.NSE===null?'UNASSESSED':cur.NSE<0?'NEGATIVE_NSE':'历史分数可用，不构成风险认证'],
   ['当前输入支持',cur.input_support_status||'NO_RESULTS_FOR_SELECTION'],['经验区间状态',pi?'V1_EVALUATED_EMPIRICAL / NO_GUARANTEE':'NOT_EVALUATED'],
   ['V1 90%实际覆盖 / 均宽',pi?n(pi.coverage*100,2)+'% / '+n(pi.mean_width)+' m³/s':'N/A'],
   ['2018年后新时期验证',rs.P6.status],['业务认证',rs.business_certification],['所选月Qsim',n(cur.qsim)+' m³/s'],
   ['Qsim快照',cur.qsim_source_snapshot_id||'N/A'],['评价快照',cur.evaluation_source_snapshot_id||'N/A']])});
 }else if(ctx.layer==='results'&&ctx.sub==='report'||ctx.layer==='evidence'){
  var report=await get('results/report',{dataset:DS,id:V.state.publicReport});
  html+=resultSub(ctx)+V.card({title:'P4/P5科研报告、模型卡与许可',body:cat.reports.map(function(r){return '<button class="btn" data-r2-report="'+r.id+'">'+({p4_report:'P4科研报告',p5_report:'P5科学报告',model_card:'模型卡',license:'来源许可与署名'}[r.id])+'</button>';}).join('')+'<p class="mono">SHA256 '+report.sha256+'</p><pre class="r2-report">'+V.e(report.content)+'</pre>'});
 }else if(ctx.layer==='model'){
  html+=V.card({title:'P4-V2正式保存模型 · 27站 / 54模型',lead:'P2-L1为默认研究模型；C0+PT强制基线。SHRINK未晋升。只读展示不授予动态运行权限。',body:'<button class="btn" id="r2Execute">验证原模型执行门禁</button> <span id="r2ExecResult"></span>'+V.table(['站点','模型','训练截止','模型版本','参数哈希'],cat.models.map(function(r){return [{html:'<button class="btn small" data-r2-station="'+r.station_uid+'" data-r2-model="'+r.model_id+'">ID'+r.gauge_id+'</button>'},r.model_id,r.training_cutoff,r.model_version,{html:'<span class="mono">'+r.parameters_hash.slice(0,20)+'…</span>'}];}))});
 }else if(ctx.layer==='data'){
  var source=await get('selection-source',scope(cat,{station:V.state.station,start:V.state.publicStart,end:V.state.publicEnd}));
  var globalRows=[['TEMPORAL_HOLDOUT','P4-V1',cat.releases.TEMPORAL_HOLDOUT.source_snapshot_id,'1798预测 / 899站月','独立时间外评价'],['FINAL_MODEL_APPLICATION','P4-V2/P5',cat.releases.FINAL_MODEL_APPLICATION.source_snapshot_id,'648应用预测','已训练2016期，不是新OOF'],['MASKED_GAP_EVALUATION','人工遮蔽',cat.releases.MASKED_GAP_EVALUATION.model_release_id,'24预测','确实排除目标Q标签'],['TRUE_GAP_RECONSTRUCTION','真实缺档','NO_ELIGIBLE_TRUE_GAPS',0,'不制造记录']];
  html+=V.card({title:'当前选择的关联来源',lead:'全局历史计数保持不变；下列数量仅对应当前站点、模型、类别与时间窗。',body:V.kv([['站点 / 模型',V.state.station+' / '+V.state.publicModel],['当前类别',source.prediction_kind],['时间窗',source.start+' → '+source.end],['关联预测条数',source.selected_records],['该站模型类别全部条数',source.station_model_kind_total],['精确来源快照',source.source_scope.source_snapshot_id],['模型发布',source.source_scope.model_release_id]])});
  html+=V.card({title:'公开科研数据来源目录 · 全局四类',body:V.table(['当前来源','来源','精确身份','全局记录','用途'],globalRows.map(function(r){return [{html:r[0]===V.state.publicKind?'<strong data-current-source="'+r[0]+'">当前来源</strong>':'—'},r[1],r[2],r[3],r[4]];}))});
 }else{
  var d=await get('results/station',scope(cat,{station:V.state.station}));ev=await get('results/evaluation',scope(cat,{station:V.state.station},'TEMPORAL_HOLDOUT'));
  rows=d.records.filter(function(r){var date=r.year+'-'+String(r.month).padStart(2,'0');return date>=V.state.publicStart&&date<=V.state.publicEnd;});
  var evalrow=ev.records[0],first=rows[0];
  if(ctx.layer==='overview')html+=V.card({title:'公开流域历史校准月尺度径流重建',body:'<div class="kpis">'+V.kpi('已保存模型','54','27站×2公式')+V.kpi('独立评价站','25','原V1模型')+V.kpi('合法测试站月','899','2015–2017')+V.kpi('真缺档','0','NO_ELIGIBLE_TRUE_GAPS')+'</div>'});
  if(ctx.layer==='results')html+=resultSub(ctx);
  html+=V.card({title:'ID'+st.gauge_id+' · '+st.name+' · '+V.state.publicModel,lead:V.state.publicKind+'；所选范围 '+V.state.publicStart+' → '+V.state.publicEnd,body:chart(rows)+V.banner('info',V.state.publicKind,V.state.publicKind==='FINAL_MODEL_APPLICATION'?'V2最终模型应用；2016已参与训练，不是新的独立测试。':V.state.publicKind==='MASKED_GAP_EVALUATION'?'人工遮蔽实验，不是真正历史缺档。':'原V1模型2015–2017时间外评价。')+(first?'<div class="mono">snapshot='+V.e(first.source_snapshot_id)+'<br>release='+V.e(first.model_release_id)+'<br>model_hash='+first.model_hash+'</div>':'')});
  html+=V.card({title:'原V1独立评价 · '+V.state.publicModel,lead:'该评分属于V1原模型，不是V2的新测试。',body:evalrow?V.table(['NSE','KGE','RMSE','MAE','PBIAS %','合法月'],[[val(evalrow.NSE),val(evalrow.KGE),n(evalrow.RMSE),n(evalrow.MAE),n(evalrow.PBIAS,2),evalrow.n_months]]):V.empty('NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT')});
  if(evalrow)html+=V.card({title:'原V1逐年指标及经验区间',body:V.table(['年份','月数','NSE','KGE','RMSE','MAE','PBIAS %'],ev.yearly.map(function(r){return [r.year,r.n_months,val(r.NSE),val(r.KGE),n(r.RMSE),n(r.MAE),n(r.PBIAS,2)];}))+V.table(['名义覆盖','实际覆盖','均宽 m³/s'],ev.coverage.map(function(r){return [n(r.nominal*100,0)+'%',n(r.coverage*100,2)+'%',n(r.mean_width)];}))});
  var detail=await get('diagnostics',scope(cat,{station:V.state.station}));
  html+=decompositionCard(detail,rows);
  side+=V.card({title:'所选结果身份',tight:true,body:V.kv([['训练截止',first?first.training_cutoff:'N/A'],['模型版本',first?first.model_version:'N/A'],['结果记录',rows.length],['来源快照',d.scope.source_snapshot_id],['河段结果','REACH_PREDICTION_NOT_AVAILABLE']])});
 }
 html+='</div>';return {html:html,side:side,mount:function(root){mount(root,ctx);}};
}
['overview','layers','data','model','results','evidence'].forEach(function(layer){V.views[layer]=function(ctx){
 if(V.state.dataset===DS)return publicView(ctx);
 if(V.state.dataset==='SYRDARYA')return V.get('/api/vhs/health').then(function(h){if(h.r2_candidate&&!h.r2_candidate.teacher_source_mounted)return {html:V.card({title:'Syr Darya · 原研究模块保留',body:V.banner('warn','TEACHER_SOURCE_NOT_MOUNTED_IN_CANDIDATE','本地候选不挂载真实教师Q；原适配器、历史页面与执行403代码保留，合成夹具回归单独验收。没有用公开模型覆盖锡尔河结果。')}),side:''};return original[layer](ctx);});
 return original[layer](ctx);
};});
})();