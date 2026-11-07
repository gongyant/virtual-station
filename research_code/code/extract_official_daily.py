"""Safe selective extraction from independently downloaded official daily archive."""
import hashlib,json,re,tarfile,time
from pathlib import Path,PurePosixPath
R=Path(__file__).resolve().parents[1];archive=R/"source/archive/2_LamaH-CE_daily.tar.gz";out=R/"source/extracted"
assert archive.is_file()
members=[];selected=[];names=set();total=0;start=time.monotonic()
with tarfile.open(archive,mode="r|gz") as tar:
 for i,m in enumerate(tar):
  p=PurePosixPath(m.name)
  if p.is_absolute() or ".." in p.parts or "\\" in m.name or m.issym() or m.islnk() or not (m.isfile() or m.isdir()):raise ValueError("UNSAFE_ARCHIVE_MEMBER")
  if m.name in names:raise ValueError("DUPLICATE_ARCHIVE_MEMBER")
  names.add(m.name);members.append({"name":m.name,"bytes":m.size,"kind":"file" if m.isfile() else "directory"})
  if i<12:print(json.dumps({"member":m.name}),flush=True)
  low=m.name.lower()
  ident=re.search(r"(?:^|/)ID_(\d+)\.csv$",m.name)
  isdocs=("info" in [x.lower() for x in p.parts]) or "readme" in low or "license" in low
  isdata=ident and int(ident.group(1))<=50 and (("d_gauges/" in low and "/daily/" in low) or ("a_basins_total_upstrm/" in low and "/daily/" in low))
  isattrs=m.isfile() and "d_gauges/1_attributes/" in low and low.endswith(".csv")
  if m.isfile() and (isdocs or isdata or isattrs):
   if m.size>64*1024*1024:raise ValueError("UNEXPECTED_LARGE_MEMBER")
   target=out.joinpath(*p.parts).resolve()
   if not target.is_relative_to(out.resolve()) or target.exists():raise ValueError("EXTRACTION_PATH_COLLISION")
   target.parent.mkdir(parents=True,exist_ok=True)
   content=tar.extractfile(m).read();assert len(content)==m.size
   with target.open("xb") as f:f.write(content)
   selected.append({"file":str(target.relative_to(out)),"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()})
   total+=len(content)
  if i and i%800==0:print(json.dumps({"members_scanned":i,"selected":len(selected),"elapsed_s":round(time.monotonic()-start,1)}),flush=True)
(R/"source/ARCHIVE_MEMBERS.json").write_text(json.dumps(members,indent=2),encoding="utf-8")
(R/"source/EXTRACTED_FILES.json").write_text(json.dumps({"members":len(members),"selected_files":selected,"selected_bytes":total,"safety":"no traversal, links, special types, collisions; subset IDs<=50; total upstream daily forcings and gauge daily Q + Info only","hourly_data_extracted":False},indent=2),encoding="utf-8")
print(json.dumps({"members":len(members),"selected_files":len(selected),"selected_MiB":round(total/2**20,1),"elapsed_s":round(time.monotonic()-start,1)}),flush=True)

