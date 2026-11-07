from p5lib import *
demo=cr(P/"P5_APPLICATION_DEMO.csv")
# Single-panel Python report figure: all12months, both frozen masked models, genuine public Q.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,r"C:\Users\Administrator\.codex\skills\nature-figure\scripts")
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({"font.family":"sans-serif","font.sans-serif":["Arial","Helvetica","DejaVu Sans"],"font.size":8,"pdf.fonttype":42,"svg.fonttype":"none","axes.spines.top":False,"axes.spines.right":False,"legend.frameon":False})
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
