/* WEB-S1: original VHS router/shared state, selected-station frozen evidence only. */
(function(){
'use strict';var V=window.VHS,DS='LAMAH_CE_PUBLIC_V1',old=V.views.results,base='/api/v6/candidate-public/research/';
function n(x,d){return x===null||x===undefined||!Number.isFinite(Number(x))?'N/A':Number(x).toFixed(d===undefined?3:d);}
function pct(x){return x===null||x===undefined?'N/A':n(x*100,2)+'%';}
function nav(sub){return V.subnav('results',[{key:'index',label:'站点结果'},{key:'evaluation',label:'V1评价'},{key:'spatial',label:'空间结果'},{key:'report',label:'P4/P5报告'},{key:'research',label:'P6外部验证与解释'},{key:'p7',label:'P7实验候选'}],sub);}
function lineChart(rows,fields,title){
 if(!rows.length)return V.empty('此选择没有封存记录；不插值，不补零。');
 var all=rows.flatMap(function(r){return fields.map(function(f){return r[f[0]];}).filter(function(x){return x!==undefined&&x!==null;});});if(!all.length)return V.empty('无合法数值');
 var lo=Math.min(0,...all),hi=Math.max(...all),span=hi-lo||1;function X(i){return 58+900*i/Math.max(1,rows.length-1);}function Y(v){return 25+(hi-v)*230/span;}
 var s='<svg viewBox="0 0 1000 310" role="img" aria-label="'+V.e(title)+'">';
 for(var k=0;k<5;k++){var z=lo+span*k/4;s+='<line x1="58" x2="960" y1="'+Y(z)+'" y2="'+Y(z)+'" stroke="#dfe6ee"/><text x="2" y="'+(Y(z)+4)+'">'+n(z,1)+'</text>';}
 fields.forEach(function(f){var rr=rows.map(function(r,i){return r[f[0]]===null||r[f[0]]===undefined?null:X(i)+','+Y(r[f[0]]);});if(rr.some(function(x){return x!==null;}))s+='<polyline fill="none" stroke="'+f[1]+'" stroke-width="2.3" points="'+rr.filter(Boolean).join(' ')+'"/>';});
 s+='<text x="8" y="15">m³/s</text><text x="58" y="285">'+rows[0].date+'</text><text x="875" y="285">'+rows[rows.length-1].date+'</text></svg>';
 return s+'<div class="legend">'+fields.filter(function(f){return rows.some(function(r){return r[f[0]]!==null&&r[f[0]]!==undefined;});}).map(function(f){return '<span style="color:'+f[1]+'">'+V.e(f[2])+'</span>';}).join(' · ')+'</div>';
}
V.views.results=async function(ctx){
 if(V.state.dataset!==DS||!['research','p7'].includes(ctx.sub))return old(ctx);
 var cat=await V.get(base+'catalog?dataset='+DS);if(!V.state.station)V.state.station=DS+':2';
 var uid=V.state.station,model=V.state.publicModel,period=ctx.q.researchPeriod||V.state.researchPeriod||'2018_2020';
 V.state.researchPeriod=period;var scope=cat.periods[period];if(!scope)throw new Error('SOURCE_DATA_MISMATCH');
 var start=V.state.publicStart,end=V.state.publicEnd;if(end<scope.start||start>scope.end){start=scope.start;end=scope.end;}
 start=start<scope.start?scope.start:start;end=end>scope.end?scope.end:end;
 var local=ctx.q.local_qobs==='1',q={dataset:DS,station:uid,model:model,period:period,snapshot:scope.source_snapshot_id,start:start,end:end,local_qobs:local?'1':'0'};
 var controls='<div class="r2-controls"><label>同一站点选择'+V.select('r2Station',cat.stations.map(function(r){return {value:r.station_uid,label:'ID'+r.gauge_id+' · '+r.name+(r.P6_external_station?' · 外部36月':' · 此24站队列无记录')};}),uid)+'</label><label>研究模型'+V.select('r2Model',['P2-L1','C0+PT'],model)+'</label><label>冻结时期'+V.select('s1Period',[{value:'2018_2019',label:'2018–2019 · P6B固定模型外部评价'},{value:'2020',label:'2020 · P6C固定模型外部评价'},{value:'2018_2020',label:'2018–2020 · P6D合并后验诊断'}],period)+'</label><label>开始月<input type="month" id="s1Start" value="'+start+'"></label><label>结束月<input type="month" id="s1End" value="'+end+'"></label></div><p><a class="btn" href="'+V.href('results',null,{kind:'TEMPORAL_HOLDOUT',start:'2015-01',end:'2017-12'})+'">切到V1 2015–2017（原P4-V1模型）</a></p>';
 var html=V.banner('warn','WEB-S1 · 原四层平台科研证据模块','使用已观测目标月气象的历史月流量重建；不是提前预报、无资料站预测或业务认证。候选本地展示不等于生产发布许可。')+nav(ctx.sub)+V.card({title:'统一选择与覆盖',body:controls+V.kv([['原模型站',27],['P6B/C/D共同外部站',24],['合并配对站月 / 冻结预测','864 / 1728'],['ID611、688、818','不属于此24站共同队列；818单站P6A/P6B结果仍保留在历史报告'],['真实缺档 / 河段传播','0 / REACH_PREDICTION_NOT_AVAILABLE']])});
 var side=V.card({title:'当前结果的可信度与身份',tight:true,body:V.kv([['测站 / 模型',uid+' / '+model],['时期 / 来源',period+' / '+scope.origin],['训练截止',scope.train_cutoff],['模型身份',scope.model_release],['预测性质',scope.prediction_kind],['快照',scope.source_snapshot_id],['生产展示许可','NOT_GRANTED'],['动态执行','NOT_AUTHORIZED / HTTP403'],['业务认证','NOT_CERTIFIED']])});
 if(ctx.sub==='p7'){
  var p7=await V.get(base+'p7?dataset='+DS),r=p7.research;
  html=V.banner('warn','P7A · 独立研究候选页','以下为24站训练期总体证据；不属于所选P6时期的P4-V2结果。默认研究模型保持P2-L1，未授予生产发布或在线执行权限。')+nav(ctx.sub);
  side=V.card({title:'P7A研究来源与限制',tight:true,body:V.kv([['实验身份',r.experiment],['开发标签截止','2017-12'],['训练期验证','向前扩展窗口，五个两年块'],['协议哈希',r.protocol_hash||'见P7A冻结协议'],['模型注册哈希',r.research_model_registry_hash||'见P7A模型注册表'],['2018–2020对照','已暴露时期后验描述，非独立盲测'],['新独立确认集',r.future_holdout],['默认模型','P2-L1_UNCHANGED'],['生产许可','NOT_GRANTED'],['业务认证','NOT_CERTIFIED']])});
  html+=V.card({title:'P7A研究候选 · 默认模型保持P2-L1',lead:'训练期开发验证；2018–2020已经参与诊断设计，任何对照均非新的独立盲测。',body:V.kv([['状态',r.status],['真实外层 / 内层拟合',r.outer_fits+' / '+r.inner_fits],['未来Q进入训练',r.future_Q_reads],['真正独立确认集',r.future_holdout]])+V.table(['候选','训练期站点等权技能','改善站数','是否达到训练期门槛','含义'],Object.values(r.promotion||{}).map(function(x){return [x.model_id,pct(x.station_mean_skill),x.positive_stations+'/'+x.station_n,x.promoted?'达到研究晋升门槛':'未达到，停止晋升','非业务模型；不替换默认'];}))+ '<p class="notice">P7-SL冷季指示不等于已识别积雪；MEM是统计降水记忆，不是实测含水量。未使用测试Q重标定区间。</p>'});
 }else{
  var d=await V.get(base+'station?'+new URLSearchParams(q));
  if(d.status==='NOT_EVALUATED'){html+=V.card({title:'NOT_EVALUATED',body:V.empty(d.reason+'；不借用其他站或其他时期评分，不填0。')});}
  else{
   var met=d.metrics[0]||{},prefix=model==='P2-L1'?'L1_':'C0PT_';
   html+=V.card({title:'冻结逐月预测 · '+scope.origin,lead:'曲线日期窗与完整时期评分分别标识。全期指标来自已验收P6D；网站不fit、不重新评分。',body:lineChart(d.records,[['Qobs','#222','公开Qobs（受控本地）'],['Qsim_C0PT','#bd8b38','C0+PT'],['Qsim_L1','#246caa','P2-L1']],'冻结观测与两模型逐月对比')+'<label><input type="checkbox" id="s1Qobs" '+(local?'checked':'')+'>在受控本地单站曲线中显示公开Qobs（无批量导出接口）</label>'+V.kv([['曲线记录数',d.monthly_record_count],['评分范围',d.scope.start+'..'+d.scope.end+'（完整冻结时期）'],['绝对NSE / KGE',n(met[prefix+'NSE'])+' / '+n(met[prefix+'KGE'])],['RMSE / MAE m³/s',n(met[prefix+'RMSE'])+' / '+n(met[prefix+'MAE'])],['L1相对C0+PT的MSE技能',pct(met.MSE_skill)],['L1最坏月份',met.L1_worst_month],['L1前1 / 前3月SSE占比',pct(met.L1_top1_SSE_fraction)+' / '+pct(met.L1_top3_SSE_fraction)]])});
   var de=d.decomposition.filter(function(r){return r.model_id===model;});
   html+=V.card({title:'冻结模型可加解释 · '+model,lead:'各项来自原模型真实变换与系数。实际L1−C0PT还包含P/T系数重新分配；不等于直接L1项，不是因果识别。',body:lineChart(de,[['seasonal_baseline','#bd8b38','12月季节模板'],['qsim_raw','#246caa','冻结预测'],['P_contribution','#459669','当月P贡献'],['T_contribution','#b55265','当月T贡献'],['L1_contribution','#7754ac','直接前月P贡献']],'冻结特征贡献')+V.table(['日期','季节模板','P贡献','T贡献','前月P贡献','支持状态','模型哈希'],de.map(function(r){return [r.date,n(r.seasonal_baseline),n(r.P_contribution),n(r.T_contribution),n(r.L1_contribution),r.support_class,{html:'<span class="mono">'+V.e(r.model_hash.slice(0,18))+'…</span>'}];}))});
   var ss=d.seasonal.filter(function(r){return r.model_id===model&&r.quality_tier==='MAIN_DESCRIPTIVE';});
   html+=V.card({title:'季节失败与经验区间',lead:'DJF=同年1、2、12月；不是连续水文冬季。小样本NSE及同水系站点依赖限制仍在。',body:V.table(['季节','月数','绝对NSE','L1相对C0PT技能','RMSE'],ss.map(function(r){return [r.subset,r.n,n(r.NSE),pct(r.MSE_skill_L1_vs_C0PT),n(r.RMSE)];}))+V.table(['模型','名义覆盖','实际覆盖','均宽 m³/s','Interval Score'],d.intervals.map(function(r){return [r.model_id,pct(r.nominal),pct(r.coverage),n(r.mean_width_m3s),n(r.mean_interval_score_m3s)];}))+'<p class="notice">主分析、STRICT_SENSITIVITY及固定±1日敏感性原结果均保留；严格子集不是逐日QC认证，不能替换正式日期口径。</p>'});
  }
  html+=V.card({title:'固定失败案例与科研报告',body:[171,185,255,343,455,533,545].map(function(g){return '<button class="btn small" data-s1-station="'+DS+':'+g+'">ID'+g+'</button>';}).join('')+'<div class="chips">'+['P6B','P6C','P6D'].map(function(x){return '<button class="btn" data-s1-report="'+x+'">'+x+'冻结报告</button>';}).join('')+'</div><pre class="r2-report" id="s1Report"></pre>'});
 }
 return {html:html,side:side,mount:function(root){
  V.onChange(root,'r2Station',function(x){V.go('results',ctx.sub,{station:x,researchPeriod:period});});V.onChange(root,'r2Model',function(x){V.go('results',ctx.sub,{model:x,researchPeriod:period});});
  V.onChange(root,'s1Period',function(x){var s=cat.periods[x];V.go('results',ctx.sub,{researchPeriod:x,start:s.start,end:s.end});});
  ['Start','End'].forEach(function(x){V.onChange(root,'s1'+x,function(v){var p={researchPeriod:period};p[x.toLowerCase()]=v;V.go('results',ctx.sub,p);});});
  var cb=root.querySelector('#s1Qobs');if(cb)cb.onchange=function(){V.go('results',ctx.sub,{researchPeriod:period,local_qobs:cb.checked?'1':'0',start:start,end:end});};
  root.querySelectorAll('[data-s1-station]').forEach(function(b){b.onclick=function(){V.go('results','research',{station:b.dataset.s1Station,researchPeriod:period,start:start,end:end});};});
  root.querySelectorAll('[data-s1-report]').forEach(function(b){b.onclick=async function(){var token=V.state.token;var report=await V.get(base+'report?'+new URLSearchParams(Object.assign({},q,{report:b.dataset.s1Report})));if(token===V.state.token&&V.state.dataset===DS)root.querySelector('#s1Report').textContent='SHA256 '+report.sha256+'\n'+report.content;};});
 }};
};
})();
