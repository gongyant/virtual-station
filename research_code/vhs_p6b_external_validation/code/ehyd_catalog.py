import sys,json,concurrent.futures
from acquire import dl,R,jw
if __name__=='__main__':
 jobs=[('https://ehyd.gv.at/services/Messstellen/json','EHYD_ALL_STATIONS.json'),('https://ehyd.gv.at/services/Messstellen/info?id=200048','EHYD_INFO_200048.json'),('https://ehyd.gv.at/services/Messstellen/info?hzbnr=200048&typ=owf','EHYD_INFO_ALT_200048.json'),('https://ehyd.gv.at/chunk-HQ2JZ3RH.js','ehyd_services.js'),('https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048&file=5','EHYD_200048_file5.txt'),('https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048&file=4','EHYD_200048_file4.txt')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:r=list(pool.map(lambda j:dl(*j),jobs))
 jw(R/'external/EHYD_CATALOG_RECEIPTS.json',r)
