import re,html,sys,json,urllib.request,time
c=sys.argv[1]; stop=sys.argv[2]  # stop when a message date < stop (ISO)
def fetch(url):
    r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}); return urllib.request.urlopen(r,timeout=30).read().decode()
def parse(s):
    out=[]
    for m in re.findall(r'<div class="tgme_widget_message_wrap.*?</time>',s,re.S):
        pid=re.search(r'data-post="[^/]+/(\d+)"',m,re.I); tm=re.search(r'datetime="([^"]+)"',m)
        reply=re.search(r'tgme_widget_message_reply.*?href="[^"]+/(\d+)"',m,re.S)
        txt=re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',m,re.S)
        t=re.sub(r'<[^>]+>','',html.unescape(re.sub(r'<br/?>','\n',txt.group(1)))) if txt else ''
        out.append({"id":int(pid.group(1)) if pid else 0,"date":tm.group(1) if tm else "","reply_to":int(reply.group(1)) if reply else None,"text":t.strip()})
    return out
seen={}; before=None; pages=0
while pages<400:
    url=f"https://t.me/s/{c}"+(f"?before={before}" if before else "")
    try: ms=parse(fetch(url))
    except Exception as e: print(c,"ERR",e,file=sys.stderr); time.sleep(3); continue
    pages+=1
    if not ms: break
    for m in ms: seen[m["id"]]=m
    before=min(m["id"] for m in ms)
    if min(m["date"] for m in ms if m["date"])<stop: break
    time.sleep(0.5)
ms=sorted(seen.values(),key=lambda m:m["id"])
with open(f"{c}.jsonl","w") as f:
    for m in ms: f.write(json.dumps(m,ensure_ascii=False)+"\n")
print(c,"pages",pages,"msgs",len(ms),ms[0]["date"] if ms else "-", "->", ms[-1]["date"] if ms else "-")
