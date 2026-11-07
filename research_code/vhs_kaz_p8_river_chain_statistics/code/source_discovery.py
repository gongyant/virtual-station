from common import *
from acquire import fetch
import re
def main():
 event('QazSu_public_script_discovery','STARTED')
 s=(ROOT/'source/qazsu.html').read_text(encoding='utf-8');srcs=re.findall(r'<script[^>]*src=["\x27]([^"\x27]+)',s);main=next(x for x in srcs if x.startswith('main.'))
 fetch('qazsu_main.js','https://qazsu.gov.kz/'+main)
 p=ROOT/'source/qazsu_main.js'
 if p.is_file():
  text=p.read_text(encoding='utf-8');matches=[]
  for word in ['hydropost','hydro-station','hydrostation','hydroPost','apiUrl','baseUrl','BASE_URL','exportToExcel','Гидропосты','hydroposts','qazsu.gov.kz']:
   hits=[{'word':word,'position':m.start(),'context':text[max(0,m.start()-150):m.end()+230]} for m in list(re.finditer(re.escape(word),text))[:12]];matches.extend(hits)
  urls=sorted(set(re.findall(r'https?://[^\s"\x27`<>()]+',text)));put(ROOT/'source/QAZSU_PUBLIC_SCRIPT_DISCOVERY.json',{'script_url':'https://qazsu.gov.kz/'+main,'sha256':sha(p),'public_urls':urls,'relevant_context':matches});print(json.dumps({'urls':urls,'contexts':matches},ensure_ascii=False)[:14000])
 event('QazSu_public_script_discovery','FINISHED')
if __name__=='__main__':main()
