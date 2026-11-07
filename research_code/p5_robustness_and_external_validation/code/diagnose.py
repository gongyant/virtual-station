"""Post-hoc frozen P4 diagnostics and authentic saved masked-model application figure."""
from p5lib import *
from collections import defaultdict
q=labels("2017-12");pred=cr(P4/"P4_V1_PREDICTIONS.csv")
modelmeta={(r["gauge_id"],r["model_id"]):jl(Path(r["path"])/"model.json") for r in jl(P4/"P4_V1_MODEL_MANIFEST.json")["models"]}
rows=[]
for r in pred:
 g=int(r["gauge_id"]);mid=r["model_id"];y=q[r["sample_id"]];m=modelmeta[g,mid];a={**r,"gauge_id":g,"year":int(r["date"][:4]),"month":int(r["date"][5:]),"Qobs":y,"pred":float(r["q_hat_raw"]),"train_scale":float(np.mean(m["parameters"]["monthly_climatology"])),"flow":"LOW" if y<=m["Q20"] else "HIGH" if y>=m["Q80"] else "MIDDLE"}
 rows.append(a)
unc=[];fail=[]
def interval_diagnostic(rr,group):
 for lv in [80,90]:
  alpha=1-lv/100;valid=[r for r in rr if r[f"lower{lv}"]!="" and r[f"upper{lv}"]!=""]
  widths=[];norm=[];scores=[];normscores=[];covers=[];kappas=[]
  for r in valid:
   lo,hi=float(r[f"lower{lv}"]),float(r[f"upper{lv}"]);y=r["Qobs"];w=hi-lo;score=w+2/alpha*max(lo-y,0)+2/alpha*max(y-hi,0)
   widths.append(w);norm.append(w/r["train_scale"] if r["train_scale"]>0 else np.nan);scores.append(score);normscores.append(score/r["train_scale"] if r["train_scale"]>0 else np.nan);covers.append(lo<=y<=hi)
   kappas.append(modelmeta[r["gauge_id"],r["model_id"]]["calibration"][season(r["month"])]["kappa"])
  unc.append({**group,"nominal":lv/100,"n":len(rr),"n_defined":len(valid),"coverage":float(np.mean(covers)) if valid else None,"mean_width_m3s":float(np.mean(widths)) if valid else None,"median_width_m3s":float(np.median(widths)) if valid else None,"mean_width_over_train_Qmean":float(np.mean(norm)) if valid else None,"mean_interval_score":float(np.mean(scores)) if valid else None,"mean_normalized_interval_score":float(np.mean(normscores)) if valid else None,"mean_kappa":float(np.mean(kappas)) if valid else None})
for g in sorted({r["gauge_id"] for r in rows}):
 for mid in ["C0+PT","P2-L1"]:
  rr=[r for r in rows if r["gauge_id"]==g and r["model_id"]==mid];yearstats=[]
  for year in [2015,2016,2017]:
   yy=[r for r in rr if r["year"]==year];yearstats.append({"year":year,**metric([r["Qobs"] for r in yy],[r["pred"] for r in yy])})
  worst=max(yearstats,key=lambda r:r["MSE"]);overall=metric([r["Qobs"] for r in rr],[r["pred"] for r in rr]);delta=[float(r["pred"]-r["Qobs"]) for r in rr]
  fail.append({"gauge_id":g,"macro":rr[0]["macro"],"model_id":mid,**overall,"mean_year_NSE":float(np.mean([r["NSE"] for r in yearstats])),"median_year_NSE":float(np.median([r["NSE"] for r in yearstats])),"mean_year_RMSE":float(np.mean([r["RMSE"] for r in yearstats])),"median_year_RMSE":float(np.median([r["RMSE"] for r in yearstats])),"worst_MSE_year":worst["year"],"worst_year_NSE":worst["NSE"],"worst_year_MSE":worst["MSE"],"negative_NSE_years":sum(r["NSE"]<0 for r in yearstats),"high_confidence_suitable":"NO" if overall["NSE"]<0 or any(r["NSE"]<0 for r in yearstats) else "NOT_CERTIFIED_RESEARCH_ONLY","posthoc_not_new_validation":True})
  interval_diagnostic(rr,{"scope":"STATION","group":g,"model_id":mid})
  for ss in ["DJF","MAM","JJA","SON"]:
   interval_diagnostic([r for r in rr if season(r["month"])==ss],{"scope":"STATION_SEASON","group":f"{g}|{ss}","model_id":mid})
for mid in ["C0+PT","P2-L1"]:
 rr=[r for r in rows if r["model_id"]==mid];interval_diagnostic(rr,{"scope":"ALL_MONTHS_DESCRIPTIVE","group":"ALL","model_id":mid})
 for key in ["macro","flow","support_class","year"]:
  for value in sorted({r[key] for r in rr}):
   interval_diagnostic([r for r in rr if r[key]==value],{"scope":key,"group":value,"model_id":mid})
 for ss in ["DJF","MAM","JJA","SON","MAY_JUN"]:
  xx=[r for r in rr if (r["month"] in [5,6] if ss=="MAY_JUN" else season(r["month"])==ss)]
  interval_diagnostic(xx,{"scope":"SEASON","group":ss,"model_id":mid})
cw(P/"P5_FAILURE_DIAGNOSTICS.csv",fail);cw(P/"P5_UNCERTAINTY_DIAGNOSTICS.csv",unc);cw(P/"P5_INTERVAL_WIDTH_AND_COVERAGE.csv",unc)
# Paired diagnostics preserve exact dates, evaluate no new model and do not alter original metrics.
pairs=[]
for g in sorted({r["gauge_id"] for r in rows}):
 rr=[r for r in rows if r["gauge_id"]==g];by={mid:{r["sample_id"]:r for r in rr if r["model_id"]==mid} for mid in ["C0+PT","P2-L1"]}
 for subset in ["ALL","DJF","MAY_JUN",2015,2016,2017]:
  aa=[r for r in by["C0+PT"].values() if subset=="ALL" or subset=="DJF" and r["month"] in [12,1,2] or subset=="MAY_JUN" and r["month"] in [5,6] or r["year"]==subset]
  bb=[by["P2-L1"][r["sample_id"]] for r in aa];a=metric([r["Qobs"] for r in aa],[r["pred"] for r in aa]);b=metric([r["Qobs"] for r in bb],[r["pred"] for r in bb])
  pairs.append({"gauge_id":g,"macro":rr[0]["macro"],"subset":subset,"MSE_skill":1-b["MSE"]/a["MSE"],"MAE_change":b["MAE"]-a["MAE"],"KGE_change":b["KGE"]-a["KGE"],"PBIAS_change":b["PBIAS"]-a["PBIAS"],"abs_PBIAS_change":abs(b["PBIAS"])-abs(a["PBIAS"])})
cw(P/"P5_PAIRED_DIAGNOSTICS.csv",pairs)
demo=[]
for mid in ["C0+PT","P2-L1"]:
 source=P4/"runs/PUBLIC_DATA_FINAL_P4_MASKED_DEMO"/(mid.replace("+","_")+"_FRESH_PROCESS.csv")
 for r in cr(source):
  sid=f'LAMAH_CE_PUBLIC_V1:2:{r["date"]}'
  demo.append({"label":"PUBLIC_DATA_APPLICATION_P5","role":"REPLAY_FROZEN_P4_MASKED_OOF_NO_REFIT","observation_status":"MASKED_ACCEPTED","Qobs_m3s":q[sid],**r})
cw(P/"P5_APPLICATION_DEMO.csv",demo)
# Single-panel Python report figure: all12months, both frozen masked models, genuine public Q.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,r"C:\Users\Administrator\.codex\skills\nature-figure\scripts")
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8,"pdf.fonttype":42,"svg.fonttype":"none","axes.spines.top":False,"axes.spines.right":False,"legend.frameon":False})
fig,ax=plt.subplots(figsize=(7.2,3.6));xx=np.arange(1,13);l1=[r for r in demo if r["model_id"]=="P2-L1"];base=[r for r in demo if r["model_id"]=="C0+PT"]
ax.fill_between(xx,[float(r["lower90"]) for r in l1],[float(r["upper90"]) for r in l1],color="#b8cbd9",alpha=.5,label="L1 empirical 90% interval")
ax.plot(xx,[float(r["Qobs_m3s"]) for r in l1],color="#222222",marker="o",ms=3,lw=1.5,label="Observed public Q")
ax.plot(xx,[float(r["q_hat_raw"]) for r in base],color="#8a8a8a",ls="--",lw=1.5,label="C0+PT (masked-block fit)")
ax.plot(xx,[float(r["q_hat_raw"]) for r in l1],color="#25668a",lw=1.6,label="P2-L1 (masked-block fit)")
ax.set(xlim=(.8,12.2),xticks=xx,xlabel="Calendar month in 2016",ylabel="Monthly mean streamflow (m³/s)",title="ID2: genuine 12-month masked-observation reconstruction")
fig.text(.12,.02,"Source: LamaH-CE v1.0; frozen P4 masked models exclude all 2016 Q. Not a true historical gap.",fontsize=7)
ax.legend(fontsize=7,loc="upper right");fig.subplots_adjust(left=.1,right=.98,bottom=.2,top=.89)
fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=str(P/"figures/application.alignment.json"),overlay_svg=str(P/"figures/application.alignment.svg"),strict=True)
fig.savefig(P/"P5_APPLICATION_DEMO.png",dpi=300);fig.savefig(P/"figures/P5_APPLICATION_DEMO.pdf");fig.savefig(P/"figures/P5_APPLICATION_DEMO.svg");plt.close(fig)
attempt("P4_POSTHOC_DIAGNOSIS_COMPLETE",diagnostic_rows=len(fail),interval_groups=len(unc),no_refitting=True)
print(json.dumps({"failure_rows":len(fail),"interval_groups":len(unc),"demo_rows":len(demo)}))
