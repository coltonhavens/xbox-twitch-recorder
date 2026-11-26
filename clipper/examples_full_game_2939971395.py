import json, subprocess, os
F0=690.0; SRC='/tmp/g20/full.mp4'
W=json.load(open('/tmp/g20/words.json'))
run=lambda *c: subprocess.run(list(c),check=True)
enc=["-c:v","libx264","-preset","veryfast","-crf","18","-r","30","-c:a","aac","-b:a","192k","-ar","48000","-ac","2"]

plan=[]  # (a,b,kind,callouts[(t,label)])
plan.append(("HOOK",))
for k,lab in [(1305.0,"ONE SHOT!"),(1385.25,"ONE SHOT!"),(1437.25,"DOUBLE!"),(1558.25,"HEADSHOT!")]:
    a,b=(k-1.8,k+0.6) if k!=1437.25 else (1435.5,1438.9)
    c=[(k,lab)] if k!=1437.25 else [(1437.25,"ONE SHOT!"),(1438.25,"DOUBLE!")]
    plan.append((a,b,"burst",c))
plan += [(718.8,737.3,"talk",[]),(763.6,783.0,"talk",[])]
def kill(k,k2=None):
    a,b=k-3.0,(k2 or k)+1.0
    return (a,b,"kill",[(k,"DOWN!")]+([(k2,"DOWN!")] if k2 else []))
bites={"A":(866.7,874.6),"B":(1052.1,1057.3),"C":(1158.0,1168.1),"D":(1388.0,1396.3),"E":(1228.3,1231.3),"F":(1407.2,1411.4)}
groups=[[kill(820.25),kill(850.0),kill(916.5),"A"],
        [kill(1013.5,1015.0),kill(1046.75),kill(1066.5),"B"],
        [kill(1080.5),kill(1115.25),kill(1240.0),"C"],
        [kill(1305.0),kill(1311.0),kill(1383.5,1385.25),"D"],
        [kill(1406.25),kill(1437.25,1438.25),kill(1449.25),"E"],
        [kill(1477.5),kill(1486.0),kill(1542.0),"F"]]
for g in groups:
    plan += g[:3]; a,b=bites[g[3]]; plan.append((a,b,"bite",[]))
plan.append((1556.05,1562.6,"kill",[(1558.25,"HEADSHOT!")]))
plan.append((1588.0,1601.5,"kill",[(1600.8,"VICTORY!")]))
os.makedirs('/tmp/g20/q',exist_ok=True)
parts=[];words=[];moods=[];cum=0.0;COUNT=[]
for i,p in enumerate(plan):
    f=f"/tmp/g20/q3/{i:03d}.mp4"
    if p[0]=="HOOK":
        run("cp","/tmp/g20/p/000b.mp4",f); L=8.2
        words += [{"w":w['w'],"s":round(w['s']-1641.6,2),"e":round(w['e']-1641.6,2),"spk":"me"} for w in W if 1641.6<=w['s']<1649.6]
        moods.append([0,L,"laugh"]); parts.append(f); cum+=L; continue
    a,b,kind,calls=p
    run("ffmpeg","-v","error","-y","-ss",f"{a-F0:.3f}","-t",f"{b-a:.3f}","-i",SRC,"-vf","scale=1280:720,setsar=1",*enc,f)
    parts.append(f)
    # captions: his words in the piece; skip words that collide with a callout
    ct=[cum+t-a for t,_ in calls]
    for w in W:
        if a<=w['s']<b-0.1:
            s=cum+w['s']-a
            if any(c-0.1<=s<c+0.8 for c in ct): continue
            words.append({"w":w['w'],"s":round(s,2),"e":round(cum+w['e']-a,2),"spk":"me"})
    for t,lab in calls:
        if kind=="kill" and lab in ("DOWN!","HEADSHOT!"): COUNT.append(round(cum+t-a,2))
        s=round(cum+t-a,2); words.append({"w":lab,"s":s,"e":round(s+0.8,2),"spk":"callout"})
        moods.append([s,s+1.6,"shocked"])
    if kind=="bite": moods.append([cum,cum+b-a,"laugh"])
    cum+=b-a
words.sort(key=lambda w:w['s']); moods.sort()
open('/tmp/g20/q3/list.txt','w').write("".join(f"file '{p}'\n" for p in parts))
run("ffmpeg","-v","error","-y","-f","concat","-safe","0","-i","/tmp/g20/q3/list.txt","-c","copy","/tmp/g20/src3.mp4")
json.dump({"src":"/tmp/g20/src3.mp4","start":0,"end":round(cum,2),"title":"My PERSONAL BEST:\n20 KILL WIN","words":words,"moods":moods,"out":"/tmp/g20/v3_render.mp4"},open('/tmp/g20/spec3.json','w'))
json.dump(COUNT,open('/tmp/g20/count_times.json','w'))
print("downs",len(COUNT),"pieces",len(parts),"length",round(cum,1))
