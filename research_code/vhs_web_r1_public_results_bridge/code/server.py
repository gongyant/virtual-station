"""Loopback-only isolated result preview; no training or HTTP inference."""
from core import *
from bridge import PublicResultsBridge
import argparse,urllib.parse,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import http_policy
BRIDGE=PublicResultsBridge()
class Handler(BaseHTTPRequestHandler):
 server_version="VHS-Public-WEB-R1"
 def log_message(self,*args):pass
 def send(self,status,obj,ctype="application/json; charset=utf-8"):
  body=(json.dumps(obj,ensure_ascii=False,allow_nan=False) if isinstance(obj,(dict,list)) else obj)
  if isinstance(body,str):body=body.encode("utf-8")
  self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store")
  for k,v in http_policy.SECURITY_HEADERS.items():self.send_header(k,v)
  self.end_headers()
  if self.command!="HEAD":self.wfile.write(body)
 def gate(self):
  check=http_policy.check_request(self.command,urllib.parse.urlparse(self.path).path,self.headers,self.server.server_port)
  if check:self.send(check[0],{"status":check[1],"prediction":None});return False
  return True
 def do_HEAD(self):self.do_GET()
 def do_GET(self):
  if not self.gate():return
  u=urllib.parse.urlparse(self.path);q0=urllib.parse.parse_qs(u.query,keep_blank_values=True)
  if any(len(v)!=1 for v in q0.values()):self.send(400,{"status":"DUPLICATE_PARAM"});return
  q={k:v[0] for k,v in q0.items()}
  if u.path in ["/","/index.html","/app.js","/styles.css"]:
   name="index.html" if u.path=="/" else u.path[1:];p=BASE/"static"/name
   self.send(200,p.read_bytes(),{"html":"text/html; charset=utf-8","js":"application/javascript; charset=utf-8","css":"text/css; charset=utf-8"}[p.suffix[1:]]);return
  if u.path=="/api/health":self.send(200,{"status":"LOCAL_PUBLIC_RESULTS_PREVIEW","build":"WEB-R1","production_deployed":False,"execution":"MODEL_EXECUTION_NOT_AUTHORIZED"});return
  st,out=BRIDGE.handle(u.path,q);self.send(st,out)
 def do_POST(self):
  if not self.gate():return
  self.send(403,{"status":"MODEL_EXECUTION_NOT_AUTHORIZED","prediction":None,"note":"公开展示权限与执行权限分开；原网站门禁未修改"})
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--port",type=int,default=8791);args=ap.parse_args()
 assert args.port not in [8772,8773,8774,8775],"DO_NOT_REPLACE_OLD_SITE"
 ThreadingHTTPServer(("127.0.0.1",args.port),Handler).serve_forever()
