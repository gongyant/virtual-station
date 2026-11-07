/* KAZ-N1 extends original VHS navigation/state; no fitting or synthetic national accuracy. */
(function(){
'use strict';var V=window.VHS,DS='KAZAKHSTAN_PUBLIC_NETWORK',API='/api/v6/candidate-kaz/',old={};Object.keys(V.views).forEach(function(k){old[k]=V.views[k];});
function n(v,d){return v===null||v===undefined||!Number.isFinite(Number(v))?'N/A':Number(v).toFixed(d===undefined?3:d);}
function pct(v){return v===null||v===undefined?'N/A':n(Number(v)*100,2)+'%';}
function get(leaf,cat){return V.get(API+leaf+'?'+new URLSearchParams({dataset:DS,...(cat?{snapshot:cat.source_snapshot_id}:{})}));}
function sub(ctx){return V.subnav('results',[{key:'index',label:'全国基线与实际密度'},{key:'pub',label:'欧洲PUB方法学验证'},{key:'readiness',label:'来源与数据缺口'}],ctx.sub||'index');}
function density(cat){return V.card({title:'实际等效密度 · 固定分母2,724,900 km²',lead:'以下只加入已通过对应准入的实际产物。1,230个待核验几何点不计入密度增量，也不表示增加了物理传感器。',body:V.table(['口径','实际新增合格虚拟站','等效站点数','个/km²','个/万km²'],cat.density.map(function(r){return [V.e(r.scenario),r.added_actual_virtual_count,r.equivalent_count,n(r.density_per_km2,12),n(r.density_per_10000_km2,9)];}))+'<p class="notice">河流基线394；全类型442另为 '+n(442/2724900,12)+' 个/km²。不是将2024年的377站和当前442站混为一个时点。</p>'});}
function mapSvg(d){
 var b=d.bounds,w=1000,h=590,sc=Math.min(900/(b[2]-b[0]),510/(b[3]-b[1])),ox=50+(900-(b[2]-b[0])*sc)/2,oy=30+(510-(b[3]-b[1])*sc)/2;
 function X(x){return ox+(x-b[0])*sc;}function Y(y){return oy+(b[3]-y)*sc;}
 function path(g){
  var t=g.type,cs=g.coordinates;
  function line(a,close){return a.map(function(p,i){return (i?'L':'M')+X(p[0]).toFixed(2)+' '+Y(p[1]).toFixed(2);}).join(' ')+(close?'Z':'');}
  if(t==='Polygon')return cs.map(function(a){return line(a,true);}).join(' ');
  if(t==='MultiPolygon')return cs.map(function(a){return a.map(function(c){return line(c,true);}).join(' ');}).join(' ');
  if(t==='LineString')return line(cs,false);
  if(t==='MultiLineString')return cs.map(function(a){return line(a,false);}).join(' ');
  if(t==='GeometryCollection')return g.geometries.map(path).join(' ');return '';
 }
 var out='<svg viewBox="0 0 1000 590" role="img" aria-label="哈萨克斯坦实际部分河网与未准入几何初筛点"><path d="'+path(d.boundary)+'" fill="#f4f5f5" stroke="#788696" stroke-width="1.3" fill-rule="evenodd"/>';
 out+='<g data-kaz-layer="river">'+d.rivers_partial.map(function(g){return '<path d="'+path(g)+'" fill="none" stroke="#84a7bd" stroke-width=".6"/>';}).join('')+'</g>';
 out+='<g data-kaz-layer="geometry">'+d.layers.CANDIDATE_GEOMETRY.features.map(function(p){return '<circle cx="'+X(p.x)+'" cy="'+Y(p.y)+'" r="2.1" fill="#ba8b35"><title>'+V.e(p.station_id)+' · CANDIDATE_GEOMETRY · 未准入/不可预测 · NSE=N/A</title></circle>';}).join('')+'</g><g data-kaz-layer="physical"></g><g data-kaz-layer="prediction"></g>';
 out+='<text x="50" y="565">LAEA 48°N / 68°E，坐标单位m；国界为Natural Earth概化示意。</text><text x="50" y="585">西部及部分水系空白=现有AS瓦片覆盖缺口，不代表没有河流或监测站。</text></svg>';return out;
}
async function render(ctx){
 var cat=await get('catalog');if(V.state.dataset!==DS)throw new Error('STALE_DATASET_RESPONSE');var c=cat.counts;
 var html=V.banner('warn','哈萨克斯坦全国虚拟站覆盖与精度评估','当前已核实官方基数；正式准入候选和可预测虚拟站均为0。几何点、模型预测、实测验证与理论情景严格分开。')+(ctx.layer==='results'?sub(ctx):'');
 var side=V.card({title:'范围、来源与权限',tight:true,body:V.kv([['访问日期','2026-11-03'],['网络统计年','现页未注明，不冒称年度年鉴'],['官方范围','Kazhydromet现行网页列示网络'],['模型覆盖KAZ','NOT_VALIDATED'],['哈萨克斯坦NSE / KGE','N/A / N/A'],['新几何点状态','CANDIDATE_GEOMETRY，仅初筛'],['生产展示','NOT_GRANTED'],['在线模型执行','NOT_AUTHORIZED / 403'],['受限教师Q','未读取、未挂载'],['来源快照',cat.source_snapshot_id]])});
 if(ctx.layer==='layers'){
  var d=await get('map',cat);
  html+=V.card({title:'三个独立站点图层 · 实际来源范围',lead:'真实站点图层缺少现行官方坐标，不能把442个统计点随机画到地图上；可预测图层当前为空。棕色仅为有真实河网依据的待核验几何点。',body:'<div class="chips"><label><input type="checkbox" data-layer="physical" checked>真实观测站：官方河流394，已核实可映射0</label><label><input type="checkbox" data-layer="geometry" checked>几何初筛点 '+c.N_preliminary_candidate_geometry+'（正式准入0）</label><label><input type="checkbox" data-layer="prediction" checked>可预测虚拟站 0</label></div>'+mapSvg(d)+V.kv([['本地河网实际相交河段',cat.GIS.river_reaches_intersecting_country_in_local_AS_tile],['本地L12覆盖示意国界',pct(cat.GIS.L12_union_country_coverage_fraction)],['有L12子流域多边形的初筛点',cat.GIS.valid_subbasin_polygon_points],['河段Qsim','REACH_PREDICTION_NOT_AVAILABLE']])});
  html+=basinCard(cat);
 }else if(ctx.layer==='data'||ctx.layer==='results'&&ctx.sub==='readiness'){
  var ready=await get('readiness',cat);
  html+=V.card({title:'实际数据准入与许可缺口',body:V.table(['资产','状态','实际覆盖','坐标 / Q','阻断原因'],ready.records.map(function(r){return [V.e(r.asset),V.e(r.status),V.e(r.coverage),V.e(r.coordinates)+'<br>'+V.e(r.Q_series),V.e(r.blocker)];}))});
  html+=basinCard(cat)+sourceCard(cat);
 }else if(ctx.layer==='model'||ctx.layer==='results'&&ctx.sub==='pub'){
  var pub=await get('pub',cat);
  html+=V.card({title:'欧洲PUB开发验证 · 不是哈萨克斯坦精度',lead:'目标站所有日期Q从该任务训练、调参、季节Q模板和尺度拟合中移除。供体训练≤2013，目标评分2014–2017。历史标签已在旧研究阶段暴露，不能称新盲测；未使用任何KAZ Q。',body:V.kv([['真实回归拟合 / 供体季节基线估计','126 / 48'],['遮蔽站 / 每方案唯一站月','24 / 1152'],['两方案四方法真实预测','9216条；两个方案不是48个独立流域'],['目标Q / 测试期Q进入预测角色','0 / 0'],['区域分组','Rhine、Elbe、Danube，组不均衡，不视为独立24流域']])+V.table(['协议','方法','中位NSE','均值NSE','中位KGE','NSE>0站','平均MSE技能'],pub.summary.map(function(r){return [r.scheme==='LEAVE_MACRO_REGION_OUT'?'留整片水系区域':'留一站并排除上下游嵌套供体',V.e(r.model_id),n(r.NSE_median),n(r.NSE_mean),n(r.KGE_median),r.positive_NSE_count+'/24',pct(r.skill_mean_station_equal)];}))+'<p class="notice">区域共享模型和所有负NSE完整保留。没有据此重调参数或挑选好站。NSE/KGE不是“预测准确率百分比”。</p>'});
  var details=pub.records.filter(function(r){return r.analysis==='RAW_PRIMARY'&&r.model_id==='GEOGRAPHIC_DONOR_TRANSFER';});
  html+=V.card({title:'逐站负结果 · 最近邻迁移（其他方法完整文件已交付）',body:V.table(['欧洲站ID','协议','水系','测试月数','NSE','KGE','RMSE m³/s','MAE m³/s','PBIAS %'],details.map(function(r){return ['EU ID'+r.gauge_id,r.scheme==='LEAVE_MACRO_REGION_OUT'?'区域遮蔽':'留站',V.e(r.macro),r.n,n(r.NSE),n(r.KGE),n(r.RMSE),n(r.MAE),n(r.PBIAS)];}))});
 }else{
  html+=V.card({title:'先回答导师的四个问题',body:'<ol class="ul">'+cat.four_answers.map(function(t){return '<li>'+V.e(t)+'</li>';}).join('')+'</ol>'});
  html+=V.card({title:'各阶段实际数量 · 不混同候选与能力',body:V.table(['状态','实际数量','含义'],[['PHYSICAL_GAUGE',442,'官方全类型，河流394；当前坐标图层尚未取得'],['CANDIDATE_GEOMETRY',c.N_preliminary_candidate_geometry,'真实部分覆盖初筛点，未完成现行站点去重/正式准入'],['正式准入候选 N_candidate',0,'尚无完整去重与归属依据的合格目录'],['FEATURES_AVAILABLE',0,'点位全上游汇水区/同口径驱动尚未具备'],['VIRTUAL_PREDICTION_AVAILABLE',0,'没有经过准入的KAZ预测'],['RESEARCH_ADMITTED',0,'没有合格全国虚拟站产物'],['KAZ直接观测验证',0,'VALIDATION_NOT_AVAILABLE，不填NSE=0']])});
  html+=density(cat)+basinCard(cat)+sourceCard(cat);
 }
 return {html:html,side:side,mount:function(root){root.querySelectorAll('[data-layer]').forEach(function(x){x.onchange=function(){root.querySelectorAll('[data-kaz-layer="'+x.dataset.layer+'"]').forEach(function(g){g.style.display=x.checked?'':'none';});};});}};
}
function basinCard(cat){return V.card({title:'全国八大水管理流域 · 官方名称已核实',lead:'未取得经核验的管理流域多边形，不能用HydroBASINS编号或最近名称代替官方分区。逐流域潜在候选数目前N/A。',body:V.table(['流域','边界状态','初筛点归属'],cat.basins.filter(function(r){return r.basin_id!=='UNASSIGNED';}).map(function(r){return [V.e(r.basin_name_zh),'NOT_AVAILABLE','未分配，不填0个潜在点'];}))});}
function sourceCard(cat){return V.card({title:'官方来源与口径',body:cat.official.sources.map(function(s){return '<p><a href="'+V.e(s.url)+'" target="_blank" rel="noopener noreferrer">'+V.e(s.name)+'</a><br><span class="mono">SHA256 '+V.e(s.sha256)+'</span></p>';}).join('')+'<p>全部来源快照、许可说明、GIS执行日志、欧洲PUB预测及负结果保存在独立KAZ-N1目录。原P7/P6D/WEB-S1、教师权限和默认模型保持不变。</p>'});}
['overview','layers','data','model','results','evidence'].forEach(function(layer){V.views[layer]=async function(ctx){document.querySelectorAll('#dsSwitch [data-ds]').forEach(function(b){b.setAttribute('aria-selected',String(b.getAttribute('data-ds')===V.state.dataset));});return V.state.dataset===DS?render(ctx):old[layer](ctx);};});
})();
