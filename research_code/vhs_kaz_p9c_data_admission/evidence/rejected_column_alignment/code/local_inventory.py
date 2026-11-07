from acquire import *
if __name__=='__main__':
 scopes=[ROOT.parent,Path('E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/data'),Path.home()/'Downloads',Path.home()/'Desktop']
 hits=[];roots=[]
 for base in scopes:
  roots.append(dict(path=str(base),exists=base.exists()))
  if not base.is_dir():continue
  for folder,dirs,files in os.walk(base):
   dirs[:]=[d for d in dirs if not any(t in d.lower() for t in ['quarantine','sealed_runoff','teacher','browser-profile','node_modules','.venv']) and d.lower()!='runoff']
   for name in files:
    lower=name.lower()
    if not lower.endswith(('.xls','.xlsx','.zip')):continue
    if any(t in lower for t in ['1912','db3337','46593408']) or ('哈萨克' in name and '逐月' in name):
     p=Path(folder)/name;hits.append(dict(path=str(p),bytes=p.stat().st_size,content_read=False))
 js(ROOT/'evidence/NCDC_LOCAL_FILENAME_SEARCH.json',dict(scopes=roots,matching_candidates=hits,
  search_rule='filename-onlyxls/xlsx/zip1912/db3337/46593408or哈萨克+逐月;no private Q files read',
  limitation='No hit does not exclude renamed or differently located files;user asked asynchronously for existing approved path',NCDC_file_obtained=False))
 event(stage='bounded_NCDC_filename_inventory',matching_candidates=len(hits),private_Q_contents_read=False)
