from common import *
import requests,re
from urllib.parse import urljoin
links=pd.read_csv(ROOT/'source/OFFICIAL_PAGE_LINKS.csv')
selected=links[(links.title=='Archive')|(links.title=='Meteorological and hydrological databases')].drop_duplicates('url')
logs=[];discovered=[]
for r in selected.itertuples():
    out=dict(title=r.title,url=r.url,accessed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selection='exact observed official-page link; no guessed route')
    try:
        response=requests.get(r.url,timeout=(10,25));p=ROOT/'source'/('official_archive_link.html' if r.title=='Archive' else 'official_met_database_link.html');p.write_bytes(response.content)
        out.update(status=response.status_code,final_url=response.url,sha256=sha(p),bytes=len(response.content))
        for href,title in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',response.text,re.S|re.I):
            title=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',title)).strip();u=urljoin(response.url,href)
            discovered.append(dict(source=r.url,title=title,url=u,catalog_or_data_candidate=bool(re.search(r'hydro|station|catalog|post|xlsx|\.zip|csv|каталог|пост',title+' '+u,re.I))))
    except Exception as e:out['error']=str(e)
    logs.append(out);event('official_observed_link_attempt',**out)
js(ROOT/'source/OFFICIAL_OBSERVED_LINK_LOG.json',logs);csv(ROOT/'source/OFFICIAL_OBSERVED_LINKS.csv',discovered)
(ROOT/'source/ACCESS_LIMITS.md').write_text('官方网页访问成功；由该页实链进入 Archive 与气象水文数据库。早先猜测 /en/archive 返回站内404，已保留日志，不视为有效归档。交互地图超时。未获完整现役394站可导出目录、逐站成员认证、连续历史Q或明确批量再发布许可。数据库登录/申请边界不绕过。\n',encoding='utf-8')
