from common import *
import shutil,re,html
from PIL import Image
def main():
 event('final_metadata_and_figure_checks','STARTED')
 n1=pathlib.Path(read(ROOT/'evidence/DISCOVERY.json')['KAZ_N1']);old=read(n1/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson');lookup={x['properties']['station_id']:x['properties'] for x in old['features']}
 p=ROOT/'P8_KAZ_N1_CANDIDATE_RECHECK.csv';backup=ROOT/'evidence/CANDIDATE_RECHECK_BEFORE_AREA_METADATA_FIX.csv';assert not backup.exists();shutil.copy2(p,backup);rows=list(csv.DictReader(p.open(encoding='utf-8-sig')))
 for r in rows:
  src=lookup[r['station_id']];r['source_upstream_area_outlet_proxy_km2']=src['upstream_area_at_reach_outlet_km2'];r['source_upstream_area_lower_bound_km2']=src['upstream_area_lower_bound_km2'];assert src['point_specific_upstream_area_km2'] is None
 csvout(p,rows);put(ROOT/'evidence/CANDIDATE_AREA_METADATA_CHECK.json',{'checked':len(rows),'passed':len(rows),'failed':0,'correction':'source field key is upstream_area_at_reach_outlet_km2; initial copied proxy column empty due wrong key, no geometry/status/length/count or admission changes','original_source_unchanged':True,'exact_point_catchment_still_unavailable':True,'before_sha256':sha(backup),'after_sha256':sha(p)})
 s=html.unescape(re.sub('<[^>]+>',' ',(ROOT/'source/official_network.html').read_text(encoding='utf-8')));s=' '.join(s.split());assert '442 observation posts' in s and re.search(r'river post\s*[–-]\s*394',s)
 i=s.find('442 observation posts');put(ROOT/'evidence/OFFICIAL_BASELINE_CURRENT_CHECK.json',{'access_date':now()[:10],'source_sha256':sha(ROOT/'source/official_network.html'),'verified_text':s[i-35:i+400],'all':442,'river':394,'permanent':381,'seasonal':61,'not_a_current_coordinate_catalog':True})
 imgs=[]
 for f in (ROOT/'figures').glob('*.png'):
  with Image.open(f) as im:
   dpi=im.info.get('dpi');assert dpi and min(dpi)>299;imgs.append({'file':f.name,'pixels':list(im.size),'dpi':list(dpi),'sha256':sha(f),'actual_raster_dpi_verified':True})
 put(ROOT/'evidence/FIGURE_RENDERED_QA.json',{'PNG_metadata_passed':len(imgs),'PNG_metadata_failed':0,'images':imgs,'manual_visual_review':['national map: eight labels legible, no omitted Baykonur hole, no invented virtual points','density: explicit provisional subset numerator, complete394N_A shown, categories and units visible','length:8basin all-order stacked totals, clear class1-4+ colors, no synthetic data'],'source_preflight_FALSE_POSITIVE':'validator regex (dpi|res) matches suffix res=3 in event(...,figures=3); real DPI300 read from PNG, detector result retained without forging PASS','PDF_glyph_floor':'all3PDF >=9pt; independent glyph auditor PASS','PDF_collision_validation':'NOT_AUDITABLE: PyMuPDF not installed; no install or fabricated collision pass','alignment':'single axes per chart, N/A for comparable-panel alignment','group_meeting_not_submission_certification':True})
 (ROOT/'P8_FIGURE_QA_NOTES.md').write_text('''# 图形验收范围

三图均由真实GPKG/CSV生成，PNG实际300dpi，PDF/SVG保留可编辑文字。人工逐图检查了地图（含拜科努尔区域）、八流域长度柱图和三级临时站点密度图，标题、单位、来源、图例与限制可读；原始全精度统计未使用显示简化几何。

独立PDF字号检查三图全部通过，最小9pt。源代码预检保留了一个明确误报：其正则`(dpi|res)`把日志参数`figures=3`的后缀识别成分辨率3；实际PNG元数据为299.9994dpi。未将原工具退出码1伪写为通过。无TIFF、330mm宽度是组会用途与非投稿规格的已说明选择。图形碰撞审计因PyMuPDF缺失退出2，标记NOT_AUDITABLE；没有声称自动碰撞检查通过或期刊生产验收完成。
''',encoding='utf-8')
 event('final_metadata_and_figure_checks','FINISHED',candidate_area_checks=len(rows),figure_metadata_checks=len(imgs),official_baseline_checks=1)
if __name__=='__main__':main()
