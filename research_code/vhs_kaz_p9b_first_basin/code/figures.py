from common import *
import geopandas as gpd, pyogrio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
sys.path.insert(0,str(Path('C:/Users/Administrator/.codex/skills/nature-figure/scripts')))
from audit_panel_alignment import require_matplotlib_panel_alignment

# Evidence contract: two separate single-panel geographic evidence maps.
# No predicted Q, certified identity or exact point catchment is implied.
js(ROOT/'figures/FIGURE_CONTRACT.json',dict(backend='python',archetype='quantitative grid',
    conclusions=['CA Kazakhstan series are outside the target basin; bulletin provenance only provisionally corroborates local sites',
                 'Thirty candidate records have outlet proxies, not exact point catchments; foreign upstream is retained'],
    export='7.2 by 6.2 inch research maps; PDF/SVG editable text; PNG300dpi',
    statistics='Geometry/data-coverage depiction only; no model scores or inferential replication',
    exclusions='No source station excluded; 6 CA metadata sites and all 49 provisional local sites shown. Second map displays the largest upstream proxy for legibility; all 30 remain in the GIS and status CSV.'))
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
    'font.size':8,'axes.titlesize':10,'pdf.fonttype':42,'svg.fonttype':'none',
    'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})
gp=ROOT/'P9B_FIRST_BASIN_GIS.gpkg';source=P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg'
country=pyogrio.read_dataframe(source,layer='country_boundary').to_crs(6933)
basin=pyogrio.read_dataframe(gp,layer='management_basin').to_crs(6933)
gauges=pyogrio.read_dataframe(gp,layer='provisional_gauges49').to_crs(6933)
points=pyogrio.read_dataframe(gp,layer='engineering_candidates').to_crs(6933)
proxy=pyogrio.read_dataframe(gp,layer='upstream_L12_outlet_proxies').to_crs(6933)
meta=pd.read_csv(ROOT/'data/CA_KAZ_GAUGE_METADATA.csv',dtype={'CODE':str})
ca=gpd.GeoDataFrame(meta,geometry=gpd.points_from_xy(meta.LON,meta.LAT),crs=4326).to_crs(6933)

def finish(fig,ax,name,caption):
    ax.set_aspect('equal');ax.set_axis_off()
    title=ax.get_title(loc='left');ax.set_title('',loc='left')
    fig.suptitle(title,x=.06,y=.97,ha='left',fontsize=10)
    legend=ax.get_legend()
    legend.set_bbox_to_anchor((.06,.91),transform=fig.transFigure)
    fig.text(.07,.035,caption,fontsize=7,va='bottom')
    fig.subplots_adjust(left=.04,right=.98,bottom=.16,top=.68)
    require_matplotlib_panel_alignment(fig,json_out=str(ROOT/'figures'/f'{name}.alignment.json'),strict=True)
    fig.savefig(ROOT/'figures'/f'{name}.pdf',facecolor='white')
    fig.savefig(ROOT/'figures'/f'{name}.svg',facecolor='white')
    fig.savefig(ROOT/'figures'/f'{name}.png',dpi=300,facecolor='white')
    plt.close(fig)

fig,ax=plt.subplots(figsize=(7.2,6.2))
country.plot(ax=ax,color='#eeeeee',edgecolor='#8b8b8b',linewidth=.6)
basin.plot(ax=ax,color='#dce7ee',edgecolor='#516779',linewidth=.8)
gauges.plot(ax=ax,color='#5a5a5a',markersize=7,alpha=.8)
ca.plot(ax=ax,color='#b8754f',marker='s',markersize=20)
ca[ca.CODE=='16390'].plot(ax=ax,color='#b8754f',marker='*',markersize=95,edgecolor='black',linewidth=.4)
ax.set_title('First-basin public Q coverage and provisional gauge locations',loc='left')
handles=[Patch(facecolor='#dce7ee',edgecolor='#516779',label='Balkhash-Alakol management basin'),
 Line2D([],[],marker='o',color='none',markerfacecolor='#5a5a5a',markersize=4,label='49 geometrically provisional local gauges'),
 Line2D([],[],marker='s',color='none',markerfacecolor='#b8754f',markersize=5,label='6 CA Kazakhstan gauge locations; all outside basin'),
 Line2D([],[],marker='*',color='none',markerfacecolor='#b8754f',markersize=9,label='16390: 492 monthly values, outside target')]
ax.legend(handles=handles,loc='upper left',fontsize=7,bbox_to_anchor=(0,1),borderaxespad=0)
finish(fig,ax,'P9B_SOURCE_COVERAGE_MAP','Public CA-discharge v1.0 + frozen P9A metadata. EPSG:6933.\nNo first-basin CA series; bulletin records remain Q_NOT_ADMITTED.')

fig,ax=plt.subplots(figsize=(7.2,6.2))
status=pd.read_csv(ROOT/'P9B_CATCHMENT_DELINEATION_STATUS.csv')
largest=status.sort_values('proxy_geodesic_area_km2').iloc[-1].candidate_id
# Layer uses candidate_id, verified before join; boundary includes foreign area.
key='candidate_id' if 'candidate_id' in proxy else 'station_id'
big=proxy[proxy[key]==largest]
big.plot(ax=ax,color='#dce7ee',edgecolor='#516779',linewidth=.7)
basin.boundary.plot(ax=ax,color='#b7b7b7',linewidth=.5)
country.boundary.plot(ax=ax,color='#777777',linewidth=.7,linestyle='--')
main=points[points.engineering_role=='P9A_MAINSTEM_PILOT'];alt=points[points.engineering_role!='P9A_MAINSTEM_PILOT']
gauges.plot(ax=ax,color='#aaaaaa',markersize=8)
main.plot(ax=ax,color='#3d617c',markersize=18)
alt.plot(ax=ax,color='#b8754f',marker='^',markersize=22)
conflict_ids=status.loc[status.catchment_state.str.contains('SOURCE_CONFLICT'),'candidate_id']
points[points.station_id.isin(conflict_ids)].plot(ax=ax,facecolor='none',edgecolor='#a33e3e',marker='o',markersize=65,linewidth=1)
bb=big.total_bounds;pb=points.total_bounds
x0=min(bb[0],pb[0]);x1=max(bb[2],pb[2]);y0=min(bb[1],pb[1]);y1=max(bb[3],pb[3]);pad=.06*max(x1-x0,y1-y0)
ax.set_xlim(x0-pad,x1+pad);ax.set_ylim(y0-pad,y1+pad)
ax.set_title('Engineering geometry and upstream-outlet proxy precision',loc='left')
handles=[Patch(facecolor='#dce7ee',edgecolor='#516779',label='Largest full upstream L12 outlet proxy'),
 Line2D([],[],marker='o',color='none',markerfacecolor='#3d617c',markersize=5,label='20 original mainstem candidates (all nested)'),
 Line2D([],[],marker='^',color='none',markerfacecolor='#b8754f',markersize=5,label='10 tributary alternatives (source-path screen)'),
 Line2D([],[],marker='o',color='none',markerfacecolor='none',markeredgecolor='#a33e3e',markersize=7,label='1 source-host conflict, retained'),
 Line2D([],[],color='#777777',linestyle='--',label='National boundary; foreign upstream retained')]
ax.legend(handles=handles,loc='upper left',fontsize=7)
finish(fig,ax,'P9B_CANDIDATE_PROXY_MAP','30 proxy records / 29 source hosts; exact point catchments = 0. EPSG:6933.\nHost-unit uncertainty and source conflicts remain; these are not operational VHS.')
js(ROOT/'figures/FIGURE_INPUT_PROVENANCE.json',{str(p):digest(p) for p in [gp,source,ROOT/'P9B_CATCHMENT_DELINEATION_STATUS.csv',ROOT/'data/CA_KAZ_GAUGE_METADATA.csv']})
event('research_maps_rendered',map_count=2,point_exact_catchments=0)
