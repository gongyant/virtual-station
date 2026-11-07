from acquire import *
import zipfile
def archive(url,name,cap=200_000_000):
 dest=ROOT/'source'/name;part=dest.with_suffix(dest.suffix+'.part')
 if dest.exists():event(stage='reuse_raster',path=str(dest),sha256=sha(dest));return
 start=part.stat().st_size if part.exists() else 0
 headers={'Range':f'bytes={start}-'} if start else {}
 try:
  with requests.get(url,headers=headers,stream=True,timeout=(15,60)) as r:
   r.raise_for_status()
   if start and r.status_code!=206:raise RuntimeError('Refuse appending a non206 range response')
   total=start+int(r.headers.get('Content-Length',0));assert 0<total<=cap
   event(stage='raster_download_started',url=url,status=r.status_code,total_bytes=total,range_start=start)
   size=start;mark=start
   with part.open('ab' if start else 'wb') as f:
    for b in r.iter_content(1024*1024):
     f.write(b);size+=len(b)
     if size>cap:raise RuntimeError('Size cap exceeded')
     if size-mark>=16*1024*1024:event(stage='raster_download_progress',file=name,bytes=size,total_bytes=total);mark=size
   assert size==total
  with zipfile.ZipFile(part) as z:
   members=[dict(name=i.filename,bytes=i.file_size,CRC=i.CRC) for i in z.infolist()]
   assert z.testzip() is None
  part.rename(dest);js(ROOT/'evidence'/f'{name}_MEMBERS.json',members)
  event(stage='raster_download_verified',file=name,bytes=size,sha256=sha(dest),zip_CRC='PASS')
 except Exception as e:event(stage='raster_download_failed',url=url,part_bytes=part.stat().st_size if part.exists() else 0,error=repr(e))
if __name__=='__main__':
 archive('https://data.hydrosheds.org/file/hydrosheds-v1-dir/as_dir_3s/n40e070_dir.zip','n40e070_dir.zip')
 archive('https://data.hydrosheds.org/file/hydrosheds-v1-acc/as_acc_3s/N40E070_acc.zip','N40E070_acc.zip')
