import math
def vincenty(p1,p2):
 # Independent WGS84 inverse implementation, no PROJ/Geod call.
 a=6378137.;f=1/298.257223563;b=a*(1-f);lon1,lat1=map(math.radians,p1);lon2,lat2=map(math.radians,p2)
 if p1==p2:return 0.
 U1=math.atan((1-f)*math.tan(lat1));U2=math.atan((1-f)*math.tan(lat2));s1,c1=math.sin(U1),math.cos(U1);s2,c2=math.sin(U2),math.cos(U2);L=lon2-lon1;lam=L
 for _ in range(200):
  sn,cs=math.sin(lam),math.cos(lam);sins=math.hypot(c2*sn,c1*s2-s1*c2*cs)
  if sins==0:return 0.
  coss=s1*s2+c1*c2*cs;sigma=math.atan2(sins,coss);sina=c1*c2*sn/sins;cos2a=1-sina*sina;cos2m=coss-2*s1*s2/cos2a if cos2a>1e-20 else 0;C=f/16*cos2a*(4+f*(4-3*cos2a));nlam=L+(1-C)*f*sina*(sigma+C*sins*(cos2m+C*coss*(-1+2*cos2m*cos2m)))
  if abs(nlam-lam)<1e-13:break
  lam=nlam
 else:raise ValueError('VINCENTY_NOT_CONVERGED')
 usq=cos2a*(a*a-b*b)/(b*b);A=1+usq/16384*(4096+usq*(-768+usq*(320-175*usq)));B=usq/1024*(256+usq*(-128+usq*(74-47*usq)));ds=B*sins*(cos2m+B/4*(coss*(-1+2*cos2m*cos2m)-B/6*cos2m*(-3+4*sins*sins)*(-3+4*cos2m*cos2m)))
 return b*A*(sigma-ds)/1000
