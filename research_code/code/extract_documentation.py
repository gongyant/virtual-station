
import tarfile,hashlib,json
from pathlib import Path
R=Path(r"E:\VHS_Public_Baseline_Lab");items=[]
with tarfile.open(R/"source/archive/2_LamaH-CE_daily.tar.gz","r|gz") as t:
 for m in t:
  if m.isfile() and (m.name.startswith("Info_english/") or m.name.startswith("Info_deutsch/")):
   data=t.extractfile(m).read();p=R/"source/extracted"/m.name;p.parent.mkdir(exist_ok=True,parents=True)
   if p.exists():assert p.read_bytes()==data
   else:p.write_bytes(data)
   items.append({"file":m.name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
(R/"source/DOCUMENTATION_FILES.json").write_text(json.dumps(items,indent=2),encoding="utf-8")
print(json.dumps({"official_documentation_files":len(items)}))

