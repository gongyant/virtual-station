"""Python/matplotlib meeting figures; all marks trace to real P8 GIS/CSV."""
from common import *
import numpy as np,pandas as pd,geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
sys.path.insert(0,r'C:\Users\Administrator\.codex\skills\nature-figure\scripts')
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],'font.size':10,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})
COLORS=['#214c67','#438eaa','#92becb'];LAEA='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
def export(fig,name):
 out=ROOT/'figures'/name;fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=str(out)+'.alignment.json',tolerance_pt=1.5,strict=True)
 fig.savefig(str(out)+'.png',dpi=300);fig.savefig(str(out)+'.pdf');fig.savefig(str(out)+'.svg');plt.close(fig)
def main():
 (ROOT/'figures').mkdir(exist_ok=True);event('scientific_figures','STARTED')
 put(ROOT/'figures/FIGURE_CONTRACT.json',{'backend':'Python matplotlib only','purpose':'group meeting, not journal-submission certification','claim':'full-global-source clipped network order lengths are reproducible; gauge density only a provisional public catalog subset','map':'all132320 source reaches, simplify150m for display only; raw geometry used for statistics','density':'first3 ORD_CLAS grades of 8 basins; provisional QazSu subset vs complete official394 N/A, no synthetic bars','export':'PNG/PDF/SVG; fontsize>=10pt, single axes per figure; alignment single panel not applicable','QC':'source validation and PDF glyph/collision scripts plus visual QA; missing PDF parser must be reported, never claimed PASS'})
 gp=ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg';n=gpd.read_file(gp,layer='national_reaches').to_crs(LAEA);b=gpd.read_file(gp,layer='basins_source').to_crs(LAEA);country=gpd.read_file(gp,layer='country_boundary').to_crs(LAEA);q=pd.read_csv(ROOT/'P8_OFFICIAL_GAUGE_CROSSWALK.csv');q=q[q.primary_500m_geometric_match]
 fig,ax=plt.subplots(figsize=(13,8));fig.subplots_adjust(left=.07,right=.98,top=.88,bottom=.16);country.plot(ax=ax,color='#fafafa',edgecolor='#64717a',linewidth=.8);b.boundary.plot(ax=ax,color='#adb5bb',linewidth=.5)
 draw=n.copy();draw.geometry=draw.geometry.simplify(150)
 draw[draw.ORD_CLAS>=4].plot(ax=ax,color='#d8dee1',linewidth=.22,rasterized=True)
 for k in [3,2,1]:draw[draw.ORD_CLAS==k].plot(ax=ax,color=COLORS[k-1],linewidth={1:.65,2:.4,3:.3}[k],rasterized=True)
 gpd.GeoDataFrame(q,geometry=gpd.points_from_xy(q.longitude,q.latitude),crs=4326).to_crs(LAEA).plot(ax=ax,color='#9d582b',markersize=6,alpha=.8)
 for _,r in b.iterrows():
  pt=r.geometry.representative_point();label=r['name'].replace('Balkhash-Alakol','Balkhash-\nAlakol').replace('Zhaiyk-Caspian','Zhaiyk-\nCaspian');ax.text(pt.x,pt.y,label,fontsize=9,ha='center',va='center',color='#25323a',bbox={'facecolor':'white','alpha':.7,'edgecolor':'none','pad':2})
 ax.set_xlabel('LAEA easting (km; origin 68E, 48N)');ax.set_ylabel('LAEA northing (km)');ax.xaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x/1000:.0f}'));ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x/1000:.0f}'))
 fig.suptitle('Kazakhstan: complete-source HydroRIVERS network, classical orders 1–3',x=.07,ha='left',fontsize=15,fontweight='bold');fig.text(.07,.91,f'Natural Earth country clip | 8 research basin polygons | {len(q)} provisional river-gauge matches',fontsize=11)
 handles=[Line2D([0],[0],color=COLORS[k-1],lw=2,label=f'Classical {k}') for k in [1,2,3]]+[Line2D([0],[0],color='#c5cdd2',lw=2,label='Orders 4+'),Line2D([0],[0],marker='o',lw=0,color='#9d582b',markersize=4,label='Provisional QazSu subset')];fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(.06,.065),ncol=5)
 fig.text(.07,.035,'Source: HydroRIVERS v1.0; Yapiyev et al. Zenodo v2 (CC BY 4.0); QazSu public WFS, accessed 2026-11-03.',fontsize=9);fig.text(.07,.015,'Research geography, not an official surveying map. Borders/gaps retained; no virtual gauges admitted; no Qsim or gauge accuracy implied.',fontsize=9)
 export(fig,'P8_NATIONAL_ORDER_MAP')
 den=pd.read_csv(ROOT/'P8_REAL_GAUGE_DENSITY.csv');bs=den[(den.scope=='EIGHT_BASIN')&(den.ORD_CLAS_group.isin(['1','2','3']))];names=list(b.sort_values('id')['name']);fig,ax=plt.subplots(figsize=(13,7));fig.subplots_adjust(left=.09,right=.98,top=.82,bottom=.27);x=np.arange(8)
 for k in [1,2,3]:
  d=bs[bs.ORD_CLAS_group==str(k)].set_index('basin_name').reindex(names);v=d.matched_subset_density_per_1000km.values;ax.bar(x+(k-2)*.25,v,width=.23,color=COLORS[k-1],label=f'Classical {k}')
 ax.set_xticks(x,names,rotation=25,ha='right',rotation_mode='anchor');ax.set_ylabel('Provisional matched gauges / 1,000 km of river');ax.set_ylim(bottom=0);ax.legend(loc='upper right');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 fig.suptitle('River monitoring density: observed catalog subset only',x=.09,ha='left',fontsize=15,fontweight='bold');fig.text(.09,.88,'Complete official 394-gauge density by basin/order: NOT AVAILABLE (catalog identity reconciliation pending)',fontsize=11,color='#9d582b');fig.text(.09,.055,'Numerator: uniquely coded river/stream names, inside country, nearest reach <=500 m, no order/basin tie within 10 m.',fontsize=9);fig.text(.09,.03,'Denominator: geodesic clipped HydroRIVERS lengths. Not all natural streams or artificial channels; source snapshot 2026-11-03.',fontsize=9);export(fig,'P8_THREE_ORDER_GAUGE_DENSITY')
 lengths=pd.read_csv(ROOT/'P8_EIGHT_BASIN_SUMMARY.csv');ls=lengths[lengths.scope=='EIGHT_BASIN'].set_index('basin_name').reindex(names);fig,ax=plt.subplots(figsize=(13,7));fig.subplots_adjust(left=.1,right=.98,top=.86,bottom=.25);bottom=np.zeros(8)
 for key,color,label in [('class1_km',COLORS[0],'Classical 1'),('class2_km',COLORS[1],'Classical 2'),('class3_km',COLORS[2],'Classical 3'),('class4plus_km','#d5dbde','Classical 4+')]:
  vals=ls[key].values/1000;ax.bar(x,vals,bottom=bottom,color=color,label=label);bottom+=vals
 ax.set_xticks(x,names,rotation=25,ha='right',rotation_mode='anchor');ax.set_ylabel('Geodesic river-network length (1,000 km)');ax.legend(loc='upper right');fig.suptitle('Eight research basins: river-network length by classical order',x=.1,ha='left',fontsize=15,fontweight='bold');fig.text(.1,.055,'Each original HYRIV_ID contributes clipped geometry once; tributary-to-outlet paths are not repeatedly summed.',fontsize=9);fig.text(.1,.03,'Unassigned border/gap fragments are kept separately in national totals. Basin IDs and six-scope definition remain configurable.',fontsize=9);export(fig,'P8_EIGHT_BASIN_ORDER_LENGTHS')
 event('scientific_figures','FINISHED',figures=3,formats=['png','pdf','svg'])
if __name__=='__main__':main()
