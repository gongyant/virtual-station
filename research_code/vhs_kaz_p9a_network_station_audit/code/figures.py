from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import geopandas as gpd,numpy as np,pyogrio
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':10,'axes.titlesize':14,'axes.labelsize':11,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
CRS='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
def save(fig,name,source,claim):
    fig.canvas.draw();positions=[ax.get_position().bounds for ax in fig.axes]
    # Every deliverable is a single data panel; no comparable-panel alignment claim.
    js(ROOT/'figures'/f'{name}.alignment.json',dict(status='NOT_APPLICABLE_SINGLE_PANEL',axes_positions=positions))
    fig.savefig(ROOT/'figures'/f'{name}.pdf',dpi=300,bbox_inches='tight',facecolor='white')
    fig.savefig(ROOT/'figures'/f'{name}.svg',dpi=300,bbox_inches='tight',facecolor='white')
    fig.savefig(ROOT/'figures'/f'{name}.png',dpi=300,bbox_inches='tight',facecolor='white')
    js(ROOT/'figures'/f'{name}.source.json',dict(script=str(ROOT/'code/figures.py'),source=source,claim=claim,all_input_geometries_preserved=True,statistical_inference='NONE_DESCRIPTIVE_GIS',backend='Python matplotlib',dimensions_inches=list(fig.get_size_inches()),font_minimum_pt=9,projection=CRS))
    plt.close(fig)
network=pyogrio.read_dataframe(GPKG,layer='national_reaches').to_crs(CRS)
basins=pyogrio.read_dataframe(GPKG,layer='basins_source').to_crs(CRS)
country=pyogrio.read_dataframe(GPKG,layer='country_boundary').to_crs(CRS)
palette=['#12314b','#235a79','#347e9c','#659fb7','#8fbbcd','#b2ced9','#d3e0e6','#bc7d32']
for field in ['ORD_CLAS','ORD_STRA']:
    fig,ax=plt.subplots(figsize=(13,8.5));country.plot(ax=ax,facecolor='#fafafa',edgecolor='#343b42',linewidth=.7)
    for j in list(range(7,0,-1))+[8]:
        sub=network[network[field]>7] if j==8 else network[network[field]==j]
        color=palette[j-1] if field=='ORD_CLAS' else (palette[7-j] if j<8 else '#bc7d32')
        sub.plot(ax=ax,color=color,linewidth=.30 if j<4 else .20,rasterized=True)
    basins.boundary.plot(ax=ax,color='#8f959a',linewidth=.35)
    ax.set_axis_off();ax.set_title(f'Kazakhstan HydroRIVERS: {field} 1–7 and >7',loc='left',pad=14)
    handles=[]
    for j in range(1,9):
        color=palette[j-1] if field=='ORD_CLAS' else (palette[7-j] if j<8 else '#bc7d32')
        handles.append(Line2D([0],[0],color=color,lw=2,label=str(j) if j<8 else '>7 (retained)'))
    ax.legend(handles=handles,loc='lower left',ncol=4,frameon=False,title='Original global river order; not HydroBASINS level')
    fig.text(.125,.05,'132,620 original reaches | sovereign-country clip includes Baykonur | WGS84 geodesic lengths',fontsize=9)
    save(fig,'P9A_MAP_'+field,[str(GPKG),str(ROOT/'P9A_ORDER_1_TO_7.csv')],'Actual source orders above 7 are retained; inherited orders are not recalculated after clipping')
d=pd.read_csv(ROOT/'P9A_ORDER_1_TO_7.csv');d=d[d.order_scheme=='ORD_CLAS']
fig,ax=plt.subplots(figsize=(10.8,5.8));bars=ax.bar(d.order_value.astype(str),d.length_km/1000,color=[palette[min(v,8)-1] for v in d.order_value])
ax.set(xlabel='ORD_CLAS (original global classification)',ylabel='Domestic river-chain length (thousand km)',title='All actual ORD_CLAS values: 1–10')
for rect,val in zip(bars,d.length_km/1000):ax.text(rect.get_x()+rect.get_width()/2,rect.get_height()+1,f'{val:.2f}',ha='center',fontsize=9)
ax.set_ylim(0,float((d.length_km/1000).max())*1.15);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
save(fig,'P9A_ORDER_LENGTHS',[str(ROOT/'P9A_ORDER_1_TO_7.csv')],'Splitting the former 4+ group reveals the full grade distribution without changing the national total')
pilot=pyogrio.read_dataframe(ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='first_basin_pilot').to_crs(CRS)
station=pyogrio.read_dataframe(ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='qazsu_identity_audit');station=station[station.primary_500m_geometric_match & (station.nearest_basin_id==2)].to_crs(CRS)
basin=basins[basins.basin_id==2];xmin,ymin,xmax,ymax=basin.total_bounds
fig,ax=plt.subplots(figsize=(10.5,8.5));basin.plot(ax=ax,facecolor='#f6f8fa',edgecolor='#565e65',linewidth=.9)
# Display the full domestic network intersecting the selected viewport, never infer reach Q.
sub=network.cx[xmin:xmax,ymin:ymax];sub.plot(ax=ax,color='#b9cad4',linewidth=.3,rasterized=True)
station.plot(ax=ax,marker='o',color='#235a79',edgecolor='white',linewidth=.5,markersize=23,label='Provisional gauge matches (49)')
pilot.plot(ax=ax,marker='^',color='#bd7630',edgecolor='white',linewidth=.6,markersize=45,label='Engineering geometry candidates (20)')
for r in pilot.itertuples():ax.annotate(str(int(r.pilot_rank)),(r.geometry.x,r.geometry.y),xytext=(4,4),textcoords='offset points',fontsize=9,color='#774719')
ax.set_xlim(xmin-25000,xmax+25000);ax.set_ylim(ymin-25000,ymax+25000);ax.set_axis_off();ax.legend(loc='lower left',frameon=False)
ax.set_title('First geometry pilot: Balkhash–Alakol',loc='left',pad=12)
fig.text(.125,.04,'Q / homogeneous P–T / exact point catchments not admitted; formal VHS = 0. Source names are not river certification.',fontsize=9)
save(fig,'P9A_FIRST_BASIN_MAP',[str(ROOT/'P9A_FIRST_BASIN_PILOT_CANDIDATES.csv'),str(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv'),str(GPKG)],'Twenty real candidate geometries are selected by frozen geometry and topology rules; no hydrologic prediction is implied')
event('figure_render_complete',figure_count=4,formats=['PDF','SVG','PNG'],dpi=300)
