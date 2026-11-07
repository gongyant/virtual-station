from pathlib import Path
import sys,json,hashlib,re,datetime
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8');root=Path(sys.argv[1]);p=root/'source/OFFICIAL_HYDROLOGICAL_BULLETIN_2023.pdf'
if not p.is_file():raise RuntimeError('No downloaded official PDF')
reader=PdfReader(p);texts=[];hits=[]
for i,page in enumerate(reader.pages):
    text=page.extract_text() or '';texts.append(dict(page=i+1,text=text))
    for line in text.splitlines():
        if re.search(r'Balkhash|Alakol|Ili |Kapsh|Kapch|Kapshagai|monthly|гидролог|Балхаш|Алакол|Иле|Қапша|Капш|140\d\d',line,re.I):hits.append(dict(page=i+1,line=line.strip()))
(root/'source/BULLETIN_EXTRACTED_PAGES.json').write_text(json.dumps(texts,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'source/BULLETIN_SEARCH_HITS.json').write_text(json.dumps(hits,ensure_ascii=False,indent=2),encoding='utf-8')
summary=dict(pages=len(reader.pages),search_hits=len(hits),text_chars=sum(len(x['text']) for x in texts),parser='pypdf bundled runtime; original PDF read only',PDF_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),runtime=sys.executable,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(root/'evidence/BULLETIN_EXTRACTION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
