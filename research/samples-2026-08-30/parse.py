import re,html,sys
for f in sys.argv[1:]:
    s=open(f).read()
    msgs=re.findall(r'<div class="tgme_widget_message_wrap.*?</time>',s,re.S)
    print(f"\n##### {f} ({len(msgs)} msgs)")
    for m in msgs[-14:]:
        pid=re.search(r'data-post="([^"]+)"',m)
        reply=re.search(r'tgme_widget_message_reply.*?href="[^"]+/(\d+)"',m,re.S)
        txt=re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',m,re.S)
        t=html.unescape(re.sub(r'<br/?>','⏎',txt.group(1))) if txt else ''
        t=re.sub(r'<[^>]+>','',t)
        tm=re.search(r'datetime="[^"]*T([^"+]+)',m)
        media='[MEDIA]' if 'tgme_widget_message_photo' in m or 'video' in m else ''
        print((pid.group(1).split('/')[1] if pid else '?'), tm.group(1) if tm else '?', ('re:'+reply.group(1)) if reply else '', media, '|', re.sub(r'\s+',' ',t)[:260])
