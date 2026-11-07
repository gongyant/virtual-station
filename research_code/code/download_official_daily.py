"""Reproducible independent official daily acquisition. Never read historical VHS runoff copies."""
import hashlib,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1]
URL="https://zenodo.org/records/5153305/files/2_LamaH-CE_daily.tar.gz?download=1"
EXPECTED_SIZE=1477248617;EXPECTED_MD5="69fd2733e969513403f923ecc5eaa3dc"
def hashes(p):
 md5=hashlib.md5();sha=hashlib.sha256();n=0
 with p.open("rb") as f:
  for block in iter(lambda:f.read(4*1024*1024),b""):md5.update(block);sha.update(block);n+=len(block)
 return n,md5.hexdigest(),sha.hexdigest()
def main():
 p=R/"source/archive/2_LamaH-CE_daily.tar.gz";p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  part=p.with_suffix(".gz.part")
  with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"VHS-Public-Baseline-Lab/1.0"}),timeout=120) as response,part.open("xb") as out:
   for block in iter(lambda:response.read(4*1024*1024),b""):out.write(block)
  size,md5,sha=hashes(part);assert size==EXPECTED_SIZE and md5==EXPECTED_MD5;part.rename(p)
 size,md5,sha=hashes(p);assert size==EXPECTED_SIZE and md5==EXPECTED_MD5
 print(json.dumps({"source":URL,"bytes":size,"md5":md5,"sha256":sha,"hourly_download":False,"reused_historical_VHS_source":False}))
if __name__=="__main__":main()
