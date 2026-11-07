from common import *
import numpy as np,pyogrio,geopandas as gpd,shapely
from shapely.geometry import Point,LineString
from shapely.ops import substring,transform
from pyproj import Geod,Transformer,CRS
from collections import deque
G=Geod(ellps='WGS84')
country=pyogrio.read_dataframe(GPKG,layer='country_boundary').geometry.union_all()
LAEA=CRS.from_proj4('+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs')
to_xy=Transformer.from_crs(4326,LAEA,always_xy=True).transform
to_ll=Transformer.from_crs(LAEA,4326,always_xy=True).transform
def at(ids,values):
    k=np.searchsorted(ids,values);ok=k<len(ids);ok[ok]&=ids[k[ok]]==values[ok]
    return np.where(ok,k,-1)
def endpoint_distance(ax,ay,bx,by):return G.inv(ax,ay,bx,by)[2]
def orient(geom,neighbor):
    a,b=np.asarray(geom.coords)[[0,-1],:2];c,d=np.asarray(neighbor.coords)[[0,-1],:2]
    da=min(endpoint_distance(*a,*c),endpoint_distance(*a,*d));db=min(endpoint_distance(*b,*c),endpoint_distance(*b,*d))
    if min(da,db)>100 or abs(da-db)<1e-6:return None
    return geom if db<da else LineString(list(geom.coords)[::-1])
def downstream_path(node,down,limit):
    path=[];seen=set()
    while node>=0 and node not in seen and len(path)<limit:
        path.append(node);seen.add(node);node=int(down[node])
    return path
event('global_topology_start')
attrs=pyogrio.read_dataframe(GLOBAL,columns=['HYRIV_ID','NEXT_DOWN','ORD_CLAS','ORD_STRA','LENGTH_KM','UPLAND_SKM','CATCH_SKM','ENDORHEIC','MAIN_RIV'],read_geometry=False,fid_as_index=True)
attrs['source_fid']=attrs.index.astype(np.int64)
attrs=attrs.sort_values('HYRIV_ID').reset_index(drop=True)
ids=attrs.HYRIV_ID.to_numpy(dtype=np.int64);assert (np.diff(ids)>0).all()
down=at(ids,attrs.NEXT_DOWN.to_numpy());n=len(ids)
valid=np.flatnonzero(down>=0).astype(np.int32)
children=valid[np.argsort(down[valid],kind='stable')]
indptr=np.r_[0,np.cumsum(np.bincount(down[valid],minlength=n),dtype=np.int64)]
gauges=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str})
gauges=gauges[gauges.primary_500m_geometric_match].copy()
candidates=pd.read_csv(P8/'P8_KAZ_N1_CANDIDATE_RECHECK.csv')
targets=np.unique(np.r_[gauges.nearest_HYRIV_ID,candidates.historical_reach_id].astype(np.int64))
ti=at(ids,targets);assert (ti>=0).all()
mark=np.zeros(n,bool);mark[ti]=True;q=deque(ti.tolist())
while q:
    i=q.popleft()
    for child in children[indptr[i]:indptr[i+1]]:
        if not mark[child]:mark[child]=True;q.append(int(child))
ci=np.flatnonzero(mark);local=np.full(n,-1,np.int32);local[ci]=np.arange(len(ci),dtype=np.int32)
cd=np.where(down[ci]>=0,local[np.maximum(down[ci],0)],-1)
cols=attrs.iloc[ci].copy().reset_index(drop=True)
event('upstream_closure_built',global_nodes=n,target_reaches=len(targets),closure_nodes=len(ci))
need=np.unique(np.r_[ci,down[ti][down[ti]>=0]])
parts=[]
for start in range(0,len(need),25000):
    part=pyogrio.read_dataframe(GLOBAL,fids=attrs.source_fid.iloc[need[start:start+25000]].tolist(),columns=['HYRIV_ID'])
    parts.append(part)
    event('source_geometry_batch',loaded=min(start+25000,len(need)),required=len(need))
geo=pd.concat(parts,ignore_index=True).set_index('HYRIV_ID')
assert geo.index.is_unique and set(geo.index)==set(ids[need])
geom=geo.loc[cols.HYRIV_ID].geometry.to_numpy()
if any(g.geom_type!='LineString' for g in geom):raise RuntimeError('Global source non-line geometry; no silent multipart orientation')
length=np.array([G.geometry_length(g)/1000 for g in geom])
nat=pyogrio.read_dataframe(GPKG,layer='national_reaches',read_geometry=False).set_index('HYRIV_ID')
dom=nat.length_km.reindex(cols.HYRIV_ID).fillna(0).to_numpy()
foreign=np.maximum(length-dom,0)
# Every upstream edge must have an endpoint junction within frozen tolerance.
ax=shapely.get_x(shapely.get_point(geom,0));ay=shapely.get_y(shapely.get_point(geom,0))
bx=shapely.get_x(shapely.get_point(geom,-1));by=shapely.get_y(shapely.get_point(geom,-1))
edge_gap=np.full(len(ci),np.nan);vi=np.flatnonzero(cd>=0);vj=cd[vi]
edge_gap[vi]=np.minimum.reduce([G.inv(x[vi],y[vi],xx[vj],yy[vj])[2] for x,y in [(ax,ay),(bx,by)] for xx,yy in [(ax,ay),(bx,by)]])
indeg=np.bincount(cd[cd>=0],minlength=len(ci)).astype(np.int32)
degree=indeg.copy();queue=deque(np.flatnonzero(degree==0).tolist())
total=length.copy();longest=length.copy();count=np.ones(len(ci),np.int32)
fsum=foreign.copy();maxgap=np.zeros(len(ci));badcount=np.zeros(len(ci),np.int32)
main=length.copy();mainamb=np.zeros(len(ci),bool);samecount=np.zeros(len(ci),np.int16);mainchild=np.full(len(ci),-1,np.int32)
classes=cols.ORD_CLAS.to_numpy();processed=np.zeros(len(ci),bool)
while queue:
    i=queue.popleft();processed[i]=True;j=int(cd[i])
    if j<0:continue
    total[j]+=total[i];count[j]+=count[i];fsum[j]+=fsum[i]
    longest[j]=max(longest[j],length[j]+longest[i])
    maxgap[j]=max(maxgap[j],maxgap[i],edge_gap[i]);badcount[j]+=badcount[i]+int(edge_gap[i]>100)
    if classes[i]==classes[j]:
        samecount[j]+=1;mainchild[j]=i
        if samecount[j]==1:main[j]=length[j]+main[i];mainamb[j]=mainamb[i]
        else:mainamb[j]=True
    degree[j]-=1
    if degree[j]==0:queue.append(j)
cols['geometry_length_km']=length;cols['domestic_clipped_length_km']=dom;cols['foreign_length_km']=foreign
cols['downstream_local_index']=cd;cols['endpoint_gap_to_downstream_m']=edge_gap;cols['upstream_total_to_outlet_km']=total;cols['upstream_longest_to_outlet_km']=longest;cols['same_class_mainstem_to_outlet_km']=np.where(mainamb,np.nan,main)
cols['upstream_reach_count']=count;cols['upstream_foreign_length_km']=fsum;cols['upstream_bad_edge_count']=badcount;cols['mainstem_ambiguous']=mainamb;cols['DAG_processed']=processed
csv(ROOT/'data/GLOBAL_UPSTREAM_CLOSURE.csv',cols)
# Cache actual source geometry for reproduction, not modeled discharge attributes.
gpd.GeoDataFrame(cols[['HYRIV_ID','NEXT_DOWN','ORD_CLAS','ORD_STRA']],geometry=geom,crs=4326).to_file(ROOT/'data/P9A_UPSTREAM_SOURCE_GEOMETRY.gpkg',layer='source_closure',driver='GPKG',engine='pyogrio')
np.savez(ROOT/'data/TOPOLOGY_ARRAYS.npz',ids=ids,down=down,closure_global_indices=ci,closure_down=cd,mainchild=mainchild,local=local,global_source_fids=attrs.source_fid.to_numpy())
clindex={int(k):i for i,k in enumerate(cols.HYRIV_ID)}
def point_metrics(sid,rid,lon,lat,kind):
    i=clindex[int(rid)];gi=int(ci[i]);g=geom[i];neighborid=int(attrs.NEXT_DOWN.iloc[gi]);og=None;orientation='UNRESOLVED'
    if neighborid in geo.index:
        og=orient(g,geo.loc[neighborid].geometry);orientation='NEXT_DOWN_ENDPOINT'
    elif neighborid==0:
        ups=children[indptr[gi]:indptr[gi+1]]
        if len(ups):
            # orient() puts upstream shared endpoint last; reverse for terminal reach.
            u=orient(g,geo.loc[int(ids[ups[0]])].geometry)
            if u is not None:og=LineString(list(u.coords)[::-1]);orientation='TERMINAL_UPSTREAM_JUNCTION'
    row=dict(sample_kind=kind,station_id=sid,HYRIV_ID=int(rid),ORD_CLAS=int(classes[i]),ORD_STRA=int(cols.ORD_STRA.iloc[i]),longitude=lon,latitude=lat,orientation_rule=orientation,source_NEXT_DOWN=neighborid,source_ENDORHEIC=int(cols.ENDORHEIC.iloc[i]),upstream_source_reaches=int(count[i]),upstream_foreign_length_km=float(fsum[i]),cross_border_upstream=bool(fsum[i]>0.001),endpoint_bad_edge_count=int(badcount[i]),maximum_upstream_junction_gap_m=float(maxgap[i]),topology_complete_within_source_product=bool(processed[i] and badcount[i]==0),mainstem_definition='unique same ORD_CLAS continuation; not official named river source',physical_network_certified=False,exact_point_catchment_area_km2=None)
    if og is None:
        row.update(chain_status='N/A_ORIENTATION_UNRESOLVED',source_to_station_mainstem_km=None,longest_headwater_to_station_km=None,all_upstream_connected_length_km=None,within_reach_offset_km=None);return row
    xy=transform(to_xy,og);point=transform(to_xy,Point(lon,lat));s=xy.project(point);part=substring(xy,0,s)
    part_ll=transform(to_ll,part)
    offset=G.geometry_length(part_ll)/1000 if part.geom_type=='LineString' else 0.
    partial_foreign=sum(G.geometry_length(x)/1000 for x in shapely.get_parts(part_ll.difference(country)) if x.geom_type in ['LineString','MultiLineString'])
    upstream_foreign=max(float(fsum[i]-foreign[i]+partial_foreign),0.)
    snap=xy.interpolate(s);ll=transform(to_ll,snap)
    full=G.geometry_length(transform(to_ll,xy))/1000
    offset_error=abs(full-length[i]);ok=bool(processed[i] and badcount[i]==0)
    row.update(snapped_longitude=ll.x,snapped_latitude=ll.y,source_line_snap_distance_m=float(point.distance(snap)),within_reach_offset_km=float(offset),within_reach_full_length_km=float(length[i]),offset_full_roundtrip_error_km=float(offset_error),upstream_foreign_length_km=upstream_foreign,cross_border_upstream=bool(upstream_foreign>0.001),
      source_to_station_mainstem_km=float(main[i]-length[i]+offset) if ok and not mainamb[i] else None,
      longest_headwater_to_station_km=float(longest[i]-length[i]+offset) if ok else None,
      all_upstream_connected_length_km=float(total[i]-length[i]+offset) if ok else None,
      partial_graph_upstream_length_km=float(total[i]-length[i]+offset),mainstem_ambiguous=bool(mainamb[i]),
      chain_status='SOURCE_GRAPH_COMPLETE_NOT_PHYSICAL_CERTIFICATION' if ok else 'N/A_UPSTREAM_GEOMETRY_GAP_OR_CYCLE')
    return row
pointrows=[point_metrics(str(r.station_code),r.nearest_HYRIV_ID,r.longitude,r.latitude,'QAZSU_PROVISIONAL_GAUGE') for r in gauges.itertuples()]
csv(ROOT/'P9A_UPSTREAM_CHAIN_LENGTH.csv',pointrows)
crows=[point_metrics(r.station_id,r.historical_reach_id,r.longitude,r.latitude,'HISTORICAL_GEOMETRY_CANDIDATE') for r in candidates.itertuples()]
csv(ROOT/'data/CANDIDATE_CHAIN_METRICS.csv',crows)
# Directed reachability: same terminal MAIN_RIV alone is not a match.
gnodes={}
for r in gauges.itertuples():gnodes.setdefault(int(at(ids,np.array([int(r.nearest_HYRIV_ID)]))[0]),[]).append(str(r.station_code))
candidate_indices={}
for r in candidates.itertuples():candidate_indices.setdefault(int(at(ids,np.array([int(r.historical_reach_id)]))[0]),[]).append(r.station_id)
gup={}
for node,codes in gnodes.items():
    for p in downstream_path(node,down,n):
        if p in candidate_indices:
            for sid in candidate_indices[p]:gup.setdefault(sid,set()).update(codes)
connections=[]
for r in candidates.itertuples():
    idx=int(at(ids,np.array([int(r.historical_reach_id)]))[0]);downcodes=set()
    for p in downstream_path(idx,down,n):downcodes.update(gnodes.get(p,[]))
    upcodes=gup.get(r.station_id,set());connections.append(dict(station_id=r.station_id,upstream_gauge_codes='|'.join(sorted(upcodes)),downstream_gauge_codes='|'.join(sorted(downcodes)),has_directed_gauge_connection=bool(upcodes or downcodes),same_reach_direction_not_resolved=bool(idx in gnodes)))
csv(ROOT/'data/CANDIDATE_GAUGE_CONNECTIVITY.csv',connections)
ni=at(ids,nat.index.to_numpy());nd=attrs.NEXT_DOWN.iloc[ni].to_numpy();national_ids=set(nat.index)
national_missing=[int(v) for v in nd if v>0 and v not in national_ids]
national_ref=at(ids,np.array(national_missing,dtype=np.int64))
js(ROOT/'evidence/TOPOLOGY_AUDIT.json',dict(global_source_reaches=n,global_unique_ids=True,global_missing_downstream_references=int(((attrs.NEXT_DOWN.to_numpy()>0)&(down<0)).sum()),global_terminal_reaches=int((attrs.NEXT_DOWN==0).sum()),national_unique_reaches=len(nat),national_outgoing_links_outside_clip=len(national_missing),national_outgoing_references_missing_global=int((national_ref<0).sum()),closure_reaches=len(ci),closure_DAG_processed=int(processed.sum()),closure_cycles_unprocessed=int((~processed).sum()),closure_endpoint_edges_over_100m=int((edge_gap>100).sum()),provisional_gauge_chain_count=len(pointrows),gauge_mainstem_available=sum(r.get('source_to_station_mainstem_km') is not None for r in pointrows),gauge_all_upstream_available=sum(r.get('all_upstream_connected_length_km') is not None for r in pointrows),candidate_count=len(crows),mainstem_ambiguity_count=int(mainamb.sum()),scalar_NEXT_DOWN_limitation='source represents one downstream route; cannot prove absence of actual bifurcations/diversions',source_length_vs_geometry_max_abs_km=float(np.max(abs(length-cols.LENGTH_KM.to_numpy())))))
event('topology_complete',closure_reaches=len(ci),gauges=len(pointrows),candidates=len(crows),cycles=int((~processed).sum()),gaps=int((edge_gap>100).sum()))
