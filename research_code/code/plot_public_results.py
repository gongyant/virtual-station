"""Public observed/OOF hydrographs; source data are verified immutable run outputs."""
import csv,json,sys
from pathlib import Path
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/"code"))
from verify_public_run import verify_run
sys.path.insert(0,r"C:\Users\Administrator\.codex\skills\nature-figure\scripts")
from audit_panel_alignment import require_matplotlib_panel_alignment
run=next((R/"runs").glob("PUBLIC_DATA_REAL_EXPERIMENT-*"));verify_run(run)
out=R/"reports/figures";out.mkdir(exist_ok=True)
with (run/"OOF_PREDICTIONS.csv").open(encoding="utf-8") as f:data=list(csv.DictReader(f))
meta=json.loads((run/"data_provenance.json").read_text(encoding="utf-8"))
plt.rcParams.update({"font.family":"sans-serif","font.sans-serif":["Arial","Helvetica","DejaVu Sans"],"font.size":8,"axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":0.7,"pdf.fonttype":42,"svg.fonttype":"none","legend.frameon":False})
contract={"core_conclusion":"Observed public-gauge monthly discharge and genuinely held-out C0/E3n predictions; main experiment shows C0 stronger than E3n in all three preselected basins","figure_role":"validation hydrographs, all selected basins and both windows; no selective year display","archetype":"single-panel quantitative time series per basin/window","backend":"Python matplotlib","export":"PDF/SVG editable text + PNG600dpi; minimum font6pt; no submission-ready claim","uncertainty":"No interval ribbons: point OOF predictions only; year bootstrap/jackknife available in run comparison details","source":str(run/"OOF_PREDICTIONS.csv"),"license":"CC BY-SA4.0 conditions with full attribution in report; original record license discrepancy retained"}
(out/"FIGURE_CONTRACT.json").write_text(json.dumps(contract,indent=2),encoding="utf-8")
files=[]
for experiment in ("CONSECUTIVE_10Y","SPARSE_10Y_PUBLIC_SUBSAMPLING"):
 for gid in meta["selected_gauge_ids"]:
  group=[x for x in data if x["experiment"]==experiment and int(x["gauge_id"])==gid]
  by={m:sorted([x for x in group if x["model_id"]==m],key=lambda x:(int(x["year"]),int(x["month"]))) for m in ("C0","E3n")}
  dates=[];obs=[];c0=[];e3=[];last=None
  for a,b in zip(by["C0"],by["E3n"]):
   assert a["sample_id"]==b["sample_id"]
   ym=int(a["year"])*12+int(a["month"]);dt=datetime(int(a["year"]),int(a["month"]),15)
   if last is not None and ym-last>1:
    # Missing calendar years are not interpolated by a connecting line.
    dates.append(dt);obs.append(np.nan);c0.append(np.nan);e3.append(np.nan)
   dates.append(dt);obs.append(float(a["Qobs_m3s"]));c0.append(float(a["Qsim_raw_m3s"]));e3.append(float(b["Qsim_raw_m3s"]));last=ym
  fig,ax=plt.subplots(figsize=(7.2,2.9))
  fig.subplots_adjust(left=.09,right=.985,bottom=.25,top=.79)
  ax.plot(dates,obs,color="#252525",lw=1.05,label="Observed Q")
  ax.plot(dates,c0,color="#808080",lw=.9,ls="--",label="C0 OOF")
  ax.plot(dates,e3,color="#D55E00",lw=.95,label="E3n OOF")
  name=meta["selected_gauge_attributes"][str(gid)]["name"]
  label="1990–1999 consecutive" if experiment=="CONSECUTIVE_10Y" else "Fixed sparse years; gaps shown"
  ax.set_title(f"Public data | ID {gid}: {name} | {label}",fontsize=9,loc="left",pad=28)
  ax.set_xlabel("Month (UTC)");ax.set_ylabel("Monthly mean Q (m³/s)")
  ax.xaxis.set_major_locator(mdates.YearLocator(2 if experiment=="CONSECUTIVE_10Y" else 4));ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
  ax.grid(axis="y",color="#dddddd",lw=.4,zorder=0)
  ax.legend(loc="lower left",bbox_to_anchor=(0,1.01),ncol=3,fontsize=7,borderaxespad=0,handlelength=2.7)
  fig.text(.09,.06,"LamaH-CE v1.0 · DOI: 10.5281/zenodo.5153305 · 10 held-out years, 120 months; point predictions",fontsize=6)
  fig.text(.09,.025,"Q: hydrographic observations; P/T: ERA5-Land. Attribution and processing details accompany this figure.",fontsize=6)
  stem=out/f"{experiment}_ID_{gid}"
  fig.canvas.draw()
  require_matplotlib_panel_alignment(fig,json_out=str(stem)+".alignment.json",tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
  fig.savefig(str(stem)+".pdf")
  fig.savefig(str(stem)+".svg")
  fig.savefig(str(stem)+".png",dpi=600)
  plt.close(fig)
  files.append({"experiment":experiment,"gauge_id":gid,"stem":str(stem),"all120_months_shown":True,"gaps_joined":False,"type":"single_panel"})
(out/"FIGURE_INDEX.json").write_text(json.dumps(files,indent=2),encoding="utf-8")
print(json.dumps({"figures":len(files),"all_requested_basins_and_windows":True,"path":str(out)}))

