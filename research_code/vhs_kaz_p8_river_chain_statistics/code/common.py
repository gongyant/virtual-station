import pathlib,json,csv,hashlib,datetime,sys,os,time,collections
ROOT=pathlib.Path(r'E:\VHS_Public_Baseline_Lab\vhs_kaz_p8_river_chain_statistics')
LAB=ROOT.parent
REPO=pathlib.Path(r'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for c in iter(lambda:f.read(4*1024*1024),b''):h.update(c)
 return h.hexdigest()
def put(p,obj):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def csvout(p,rows):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def event(stage,status,**kw):
 with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':now(),'stage':stage,'status':status,**kw},ensure_ascii=False)+'\n')
