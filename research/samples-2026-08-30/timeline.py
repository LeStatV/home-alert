import json,re,sys
from datetime import datetime,timedelta
chs=["kpszsu","war_monitor","nebo_raketa","AerisRimor","Ukrainian_Intelligence"]
short={"kpszsu":"PS ","war_monitor":"WM ","nebo_raketa":"NR ","AerisRimor":"AR ","Ukrainian_Intelligence":"UI "}
allm=[]
for c in chs:
    for l in open(c+".jsonl"):
        m=json.loads(l); m["ch"]=c
        if not m["date"]: continue
        m["t"]=datetime.fromisoformat(m["date"].replace("+00:00","")); allm.append(m)
allm.sort(key=lambda m:m["t"])
d0,d1=sys.argv[1],sys.argv[2]
launch=re.compile(r'(баліст|☄|ціль|спуск|виход|вихід|іскандер|кинжал)',re.I)
kyiv=re.compile(r'київ|киев|столиц|бровар|бориспіл|вишгород|васильк|ірпін|обол|троєщ|позняк|дарниц|печерськ|поділ|шевченк|соломʼян|солом|голосіїв|деснян|дніпров|святош',re.I)
seeds=[m for m in allm if d0<=m["date"][:10]<=d1 and launch.search(m["text"]) and (kyiv.search(m["text"]) or re.search(r'^\W*ціль',m["text"],re.I))]
# cluster seeds within 10 min
clusters=[]
for m in seeds:
    if clusters and (m["t"]-clusters[-1][-1]["t"])<timedelta(minutes=10): clusters[-1].append(m)
    else: clusters.append([m])
for cl in clusters:
    a=cl[0]["t"]-timedelta(minutes=6); b=cl[-1]["t"]+timedelta(minutes=6)
    print(f"\n======== window {a:%m-%d %H:%M} .. {b:%H:%M} UTC ({len(cl)} seeds)")
    for m in allm:
        if a<=m["t"]<=b:
            t=re.sub(r'\s+',' ',m["text"])[:150]
            flag="*" if m in cl else " "
            print(f"{flag}{m['t']:%H:%M:%S} {short[m['ch']]}{'↩'+str(m['reply_to']) if m['reply_to'] else '      '} | {t}")
