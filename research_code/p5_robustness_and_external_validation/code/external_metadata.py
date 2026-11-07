"""Bounded official catalogue acquisition only; never download external target Q here."""
from p5lib import *
import requests,zipfile,io
out=P/"external_metadata";out.mkdir(exist_ok=False);receipts=[]
url="https://zenodo.org/api/records/17598150"
try:
 r=requests.get(url,timeout=25);r.raise_for_status();meta=r.json();jw(out/"ZENODO_17598150_METADATA.json",meta)
 wanted=[f for f in meta["files"] if f["key"] in ["streamflow_gauges.zip","README.md","appendix.zip"]]
 for f in wanted:
  assert f["size"]<4_000_000,"NO_LARGE_DOWNLOAD"
  endpoint=f["links"].get("self") or f["links"].get("content");res=requests.get(endpoint,timeout=25);res.raise_for_status();body=res.content;assert len(body)<4_000_000
  ck=f.get("checksum","")
  if ck.startswith("md5:"):assert hashlib.md5(body).hexdigest()==ck[4:]
  (out/f["key"]).write_bytes(body);receipts.append({"file":f["key"],"url":endpoint,"bytes":len(body),"sha256":sha(out/f["key"]),"advertised_checksum":ck,"UTC":now()})
  if f["key"].endswith(".zip"):
   with zipfile.ZipFile(io.BytesIO(body)) as z:
    for name in z.namelist():
     safe=Path(name);assert not safe.is_absolute() and ".." not in safe.parts
     if name.endswith((".csv",".txt",".md")):
      assert z.getinfo(name).file_size<12_000_000
      target=out/"extracted"/safe;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 jw(out/"ACQUISITION.json",{"official_record":url,"files":receipts,"external_Q_downloaded":False,"meteorology_downloaded":False,"metadata_only":True})
 print(json.dumps({"files":receipts,"extracted":[str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.suffix==".csv"]}))
except Exception as e:
 jw(out/"ACQUISITION_FAILURE.json",{"url":url,"error":repr(e),"UTC":now(),"external_Q_acquired":False});print(json.dumps({"metadata_acquisition_failed":repr(e)}))
