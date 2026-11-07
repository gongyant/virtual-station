import csv,json,hashlib,tarfile,collections,math
from pathlib import Path
import numpy as np
R=Path(r"E:\VHS_Public_Baseline_Lab"); P=R/"p1_seasonal_meteorology_ablation"
for sub in ["code","source/metadata","source/daily","evidence","runs","reports"]: (P/sub).mkdir(parents=True,exist_ok=True)
old=R/"runs/PUBLIC_DATA_REAL_EXPERIMENT-20261026T010504Z-f4d13a326504"
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def jwrite(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
def cwrite(p,rows):
 with p.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
pins={}
for line in (old/"SHA256SUMS.txt").read_text().splitlines():
 h,n=line.split("  ",1);assert sha(old/n)==h,n;pins[n]=h
jwrite(P/"evidence/FROZEN_BASELINE_PINS.json",{"run":str(old),"SHA256SUMS_sha256":sha(old/"SHA256SUMS.txt"),"files":pins})
with (old/"OOF_PREDICTIONS.csv").open() as f:rows=list(csv.DictReader(f))
groups=collections.defaultdict(list)
for r in rows:groups[(r["experiment"],int(r["gauge_id"]),r["model_id"])].append(r)
monthly=[];seasonal=[];yearly=[];summ=[]
def stat(rs):
 y=np.array([float(r["Qobs_m3s"]) for r in rs]);p=np.array([float(r["Qsim_raw_m3s"]) for r in rs])
 return {"n":len(rs),"Qobs_mean":float(y.mean()),"Qsim_mean":float(p.mean()),"bias":float((p-y).mean()),"RMSE":float(np.sqrt(np.mean((p-y)**2))),"MSE":float(np.mean((p-y)**2))}
for (ex,g,m),rs in groups.items():
 for month in range(1,13):monthly.append({"experiment":ex,"gauge_id":g,"model_id":m,"month":month,**stat([r for r in rs if int(r["month"])==month])})
 for name,ms in {"MAM":[3,4,5],"JJA":[6,7,8],"SON":[9,10,11],"DJF":[12,1,2]}.items():seasonal.append({"experiment":ex,"gauge_id":g,"model_id":m,"season":name,**stat([r for r in rs if int(r["month"]) in ms])})
for ex,g,_ in groups:
 if _!="C0":continue
 cr=groups[ex,g,"C0"];er=groups[ex,g,"E3n"]
 ds={}
 for y in sorted(set(int(r["year"]) for r in cr)):
  c=stat([r for r in cr if int(r["year"])==y]);e=stat([r for r in er if int(r["year"])==y]);ds[y]=e["MSE"]-c["MSE"]
  yearly.append({"experiment":ex,"gauge_id":g,"year":y,"C0_MSE":c["MSE"],"E3n_MSE":e["MSE"],"E3n_improvement":-ds[y]})
 total=sum(ds.values());summ.append({"experiment":ex,"gauge_id":g,"E3n_minus_C0_MSE":total/10,"1999_contribution_to_mean_gap":ds[1999]/10,"1999_signed_fraction":ds[1999]/total,"gap_without1999":sum(v for y,v in ds.items() if y!=1999)/9,"years_improved":sum(v<0 for v in ds.values())})
params=json.loads((old/"model_parameters.json").read_text())
alphas=[{"experiment":r["experiment"],"gauge_id":r["gauge_id"],"held_year":r["held_year"],**r["record"]["parameters"]["selection"]} for r in params if r["record"]["model_id"]=="E3n"]
assert len(alphas)==60 and all(r["selected_alpha"]==100 for r in alphas)
for name,rr in [("FROZEN_MONTHLY_DIAGNOSIS.csv",monthly),("FROZEN_SEASONAL_DIAGNOSIS.csv",seasonal),("FROZEN_YEARLY_DIFFERENCE.csv",yearly),("FROZEN_1999_CONTRIBUTION.csv",summ),("FROZEN_ALPHA_SELECTION.csv",alphas)]:cwrite(P/"evidence"/name,rr)
lines=["# P1 冻结基线诊断","仅重算既有 OOF、参数；未重新拟合 C0/E3n。原 run 全部文件哈希通过。","60/60 E3n 外层折选择 alpha=100；候选网格不扩大。","季节口径 MAM/JJA/SON/DJF；1999 贡献为带符号年度 MSE 差异占全部10年差异之和，并非独立因果贡献。"]
for r in summ:lines.append(f'- {r["experiment"]} ID{r["gauge_id"]}: E3n−C0 MSE={r["E3n_minus_C0_MSE"]:.6f}; 1999占差异={100*r["1999_signed_fraction"]:.1f}%; 删1999后差异={r["gap_without1999"]:.6f}; E3n改善{r["years_improved"]}/10年。')
lines+=["原三站连续十年 E3n 的3–4月高估、5–6月低估、8月高估、12月低估，逐月原值见 evidence/FROZEN_MONTHLY_DIAGNOSIS.csv。该模式不能单独识别原因；H0 对照尚未运行。","逐月、四季、逐年配对结果和参数选择证据均另存 CSV。稀疏方案与连续方案有重叠年份，不能视为独立重复。"]
(P/"P1_FROZEN_BASELINE_DIAGNOSIS.md").write_text("\n\n".join(lines),encoding="utf-8")
targets=[]
index=json.loads((R/"source/ARCHIVE_MEMBERS.json").read_text())
for x in index:
 n=x["name"]
 if "/1_attributes/" in n and n.endswith(".csv") and n.startswith(("A_basins_total_upstrm/","B_basins_intermediate_all/","D_gauges/")):targets.append(n)
with tarfile.open(R/"source/archive/2_LamaH-CE_daily.tar.gz","r|gz") as t:
 for m in t:
  if m.name not in targets:continue
  assert m.isfile() and ".." not in Path(m.name).parts
  p=P/"source/metadata"/m.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
jwrite(P/"source/METADATA_HASHES.json",{n:sha(P/"source/metadata"/n) for n in targets})
for n in targets:
 p=P/"source/metadata"/n
 with p.open(encoding="utf-8-sig") as f: print(n,":",f.readline().strip(),"\n",f.readline().strip()[:600])
print(json.dumps(summ,indent=2))

