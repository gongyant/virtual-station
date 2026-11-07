"""Idempotent, targeted R2U1 candidate patches; R2 itself remains read-only."""
from pathlib import Path
import json
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');R2=R.parent/'vhs_web_r2_host_integration';H=R/'host'
p=H/'r2_public.py';s=(R2/'host/r2_public.py').read_text(encoding='utf-8')
s=s.replace('import sys','import sys,json,hashlib,re',1)
s=s.replace('  self.candidate_local=candidate_local','''  self.candidate_local=candidate_local
  self.u1_paths={"diagnostics":R2ROOT/"diagnostics/UI_DECOMPOSITION.json","research-status":R2ROOT/"p6/P6_STATUS.json"}
  self.u1_pins={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in self.u1_paths.items() if p.exists()}''')
anchor='  st,data=self.bridge.handle('
i=s.index(anchor)
s=s[:i]+'''  leaf=path.rsplit("/",1)[-1]
  if leaf in ["diagnostics","research-status","selection-source"]:
   try:
    kind,uid,model=self.bridge.scope(q,True)
    if leaf=="selection-source":
     start=q.get("start","2015-01");end=q.get("end","2017-12")
     if not all(re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])",d) for d in [start,end]) or start>end:raise Refused(400,"INVALID_TIME_WINDOW")
     rows=[r for r in self.bridge.bundle["predictions"] if r["station_uid"]==uid and r["model_id"]==model and r["prediction_kind"]==kind]
     selected=[r for r in rows if start<=f'{r["year"]}-{r["month"]:02d}'<=end]
     data={"dataset_id":self.bridge.bundle["registry"]["dataset_id"],"station_uid":uid,"model_id":model,"prediction_kind":kind,"start":start,"end":end,"source_scope":self.bridge.releases[kind],"station_model_kind_total":len(rows),"selected_records":len(selected),"global_counts":self.bridge.bundle["counts"],"provenance_hashes":sorted({r["provenance_hash"] for r in selected}),"Qobs":None}
    else:
     p=self.u1_paths[leaf]
     if leaf not in self.u1_pins or hashlib.sha256(p.read_bytes()).hexdigest()!=self.u1_pins[leaf]:raise Refused(409,"U1_DIAGNOSTIC_SOURCE_MISMATCH")
     raw=json.loads(p.read_text(encoding="utf-8"))
     g=int(uid.rsplit(":",1)[-1])
     if leaf=="research-status":data={"station_uid":uid,"P6":next((x for x in raw["stations"] if x["gauge_id"]==g),{"gauge_id":g,"status":"NOT_RUN_NOT_IN_P6A_COHORT"}),"business_certification":"NOT_CERTIFIED"}
     else:data={"station_uid":uid,"model_id":model,"prediction_kind":kind,"summary":raw["summary"],"records":[r for r in raw["records"] if r["gauge_id"]==g and r["prediction_kind"]==kind],"station_summary":[r for r in raw["station_summary"] if r["gauge_id"]==g],"alpha":[r for r in raw["alpha"] if r["gauge_id"]==g],"definition":raw["definition"],"classification":"DESCRIPTIVE_FROZEN_DIAGNOSTICS_NOT_P6"}
    return 200,{**data,"display_scope":"USER_REQUEST_LOCAL_CANDIDATE_ONLY","production_display_permission":"NOT_GRANTED"}
   except Refused as e:return e.status,{"status":e.code,"prediction":None}
''' +s[i:]
p.write_text(s,encoding='utf-8')
s=(R2/'host/static/view_public_results.js').read_text(encoding='utf-8')
s=s.replace('/* R2:', '/* R2U1:')
start=s.index("  side+=V.card({title:'所选空间站点'");end=s.index('\n }else if',start)
s=s[:start]+'''  var hist=cur.evaluation[V.state.publicModel]||{},pi=cur.uncertainty.filter(function(r){return r.model_id===V.state.publicModel&&r.nominal===.9;})[0];
  var rs=await get('research-status',scope(cat,{station:V.state.station}));
  side+=V.card({title:'所选空间站点 · 科研状态分离',tight:true,body:V.kv([
   ['站点',cur.name],['V1评价状态',cur.NSE===null?'NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT':'GAUGE_EVALUATION_AVAILABLE'],
   ['V1 NSE / KGE',n(cur.NSE)+' / '+n(hist.KGE)],['V1误差风险',cur.NSE===null?'UNASSESSED':cur.NSE<0?'NEGATIVE_NSE':'历史分数可用，不构成风险认证'],
   ['当前输入支持',cur.input_support_status||'NO_RESULTS_FOR_SELECTION'],['经验区间状态',pi?'V1_EVALUATED_EMPIRICAL / NO_GUARANTEE':'NOT_EVALUATED'],
   ['V1 90%实际覆盖 / 均宽',pi?n(pi.coverage*100,2)+'% / '+n(pi.mean_width)+' m³/s':'N/A'],
   ['2018年后新时期验证',rs.P6.status],['业务认证',rs.business_certification],['所选月Qsim',n(cur.qsim)+' m³/s'],
   ['Qsim快照',cur.qsim_source_snapshot_id||'N/A'],['评价快照',cur.evaluation_source_snapshot_id||'N/A']])});''' +s[end:]
start=s.index("  html+=V.card({title:'公开科研数据来源目录'");end=s.index('\n }else{',start)
s=s[:start]+'''  var source=await get('selection-source',scope(cat,{station:V.state.station,start:V.state.publicStart,end:V.state.publicEnd}));
  var globalRows=[['TEMPORAL_HOLDOUT','P4-V1',cat.releases.TEMPORAL_HOLDOUT.source_snapshot_id,'1798预测 / 899站月','独立时间外评价'],['FINAL_MODEL_APPLICATION','P4-V2/P5',cat.releases.FINAL_MODEL_APPLICATION.source_snapshot_id,'648应用预测','已训练2016期，不是新OOF'],['MASKED_GAP_EVALUATION','人工遮蔽',cat.releases.MASKED_GAP_EVALUATION.model_release_id,'24预测','确实排除目标Q标签'],['TRUE_GAP_RECONSTRUCTION','真实缺档','NO_ELIGIBLE_TRUE_GAPS',0,'不制造记录']];
  html+=V.card({title:'当前选择的关联来源',lead:'全局历史计数保持不变；下列数量仅对应当前站点、模型、类别与时间窗。',body:V.kv([['站点 / 模型',V.state.station+' / '+V.state.publicModel],['当前类别',source.prediction_kind],['时间窗',source.start+' → '+source.end],['关联预测条数',source.selected_records],['该站模型类别全部条数',source.station_model_kind_total],['精确来源快照',source.source_scope.source_snapshot_id],['模型发布',source.source_scope.model_release_id]])});
  html+=V.card({title:'公开科研数据来源目录 · 全局四类',body:V.table(['当前来源','来源','精确身份','全局记录','用途'],globalRows.map(function(r){return [{html:r[0]===V.state.publicKind?'<strong data-current-source="'+r[0]+'">当前来源</strong>':'—'},r[1],r[2],r[3],r[4]];}))});''' +s[end:]
anchor="  side+=V.card({title:'所选结果身份'"
i=s.index(anchor)
s=s[:i]+'''  var detail=await get('diagnostics',scope(cat,{station:V.state.station}));
  html+=decompositionCard(detail,rows);
''' +s[i:]
# New explanation uses the actual frozen per-model template, not a substituted C0 or harmonic.
pos=s.index('async function publicView(ctx)')
s=s[:pos]+'''function decompositionCard(d,selected){
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
''' +s[pos:]
assert s.count('V1评价状态')==1 and s.count('V1误差风险')==1
(H/'static/view_public_results.js').write_text(s,encoding='utf-8')
index=(H/'static/index.html').read_text(encoding='utf-8').replace('R2原v0.6候选集成','R2U1科研解释修复候选')
(H/'static/index.html').write_text(index,encoding='utf-8')
(H/'static/styles.css').write_text((R2/'host/static/styles.css').read_text(encoding='utf-8')+'\n/* Current source identity, not a new UI theme. */\n.tblwrap tr:has([data-current-source]){background:#edf4fb;}\n[data-current-source]{color:#1f5fa8;}\n',encoding='utf-8')
status=R/'p6/P6_STATUS.json'
if not status.exists():status.write_text(json.dumps({'stations':[{'gauge_id':g,'status':'NOT_COMPLETED_NEW_Q_ADMISSION_PENDING'} for g in [818,611,688]],'production_display':'NOT_GRANTED'},ensure_ascii=False,indent=2),encoding='utf-8')
print('R2U1 targeted patches written; each risk field occurs once. Host port8793.')
