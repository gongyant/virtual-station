"""Reconfigure six names without modifying any original eight-basin data."""
from common import *
import argparse,geopandas as gpd
def main():
 a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--output',required=True);args=a.parse_args();cfg=read(args.config);names=cfg['basin_names'];assert len(names)==len(set(names))==6
 dest=pathlib.Path(args.output);assert dest.resolve().is_relative_to(ROOT.resolve()) and not dest.exists(),'NEW_P8_OUTPUT_REQUIRED'
 f=gpd.read_file(ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg',layer='basin_fragments');assert set(names)<=set(f.basin_name);f=f[f.basin_name.isin(names)];rows=[]
 for col in ['ORD_CLAS','ORD_STRA']:
  for k in ['1','2','3','4_PLUS','ALL']:
   d=f if k=='ALL' else f[f[col]>=4] if k=='4_PLUS' else f[f[col]==int(k)];rows.append({'scope_id':cfg.get('scope_id','CUSTOM_SIX'),'basin_names':'|'.join(names),'order_system':col,'order_group':k,'river_length_km':float(d.length_km.sum()),'unique_source_reaches':int(d.HYRIV_ID.nunique()),'config_sha256':sha(args.config)})
 csvout(dest,rows);print('NEW_CONFIGURED_SCOPE_WRITTEN',dest)
if __name__=='__main__':main()
