from pathlib import Path
import json,sys,re,hashlib
from pypdf import PdfReader
root=Path(sys.argv[1]);p=root/'source/WB_FLOOD_TECHNICAL_REPORT_EN.pdf'
texts=[dict(page=i+1,text=page.extract_text() or '') for i,page in enumerate(PdfReader(p).pages)]
(root/'source/WB_REPORT_EXTRACTED.json').write_text(json.dumps(texts,ensure_ascii=False,indent=2),encoding='utf-8')
hits=[dict(page=r['page'],line=line.strip()) for r in texts for line in r['text'].splitlines() if re.search(r'daily.*observ|GRDC|Tauturgen|Sarytog|Tekeli|discharge record|local institutes|1936|1981.?1990',line,re.I)]
(root/'evidence/WB_OBSERVATION_SOURCE_EVIDENCE.json').write_text(json.dumps(dict(PDF_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pages=len(texts),hits=hits),ensure_ascii=False,indent=2),encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8');print(json.dumps(hits,ensure_ascii=False)[:9000])
