import numpy as np, json, itertools
from game import analytic, NSYM, S, W, build_strips, scatter_ok
from tune_valid import valid
b1=[1,2,2,3,3,4,5,6,6,7]; bm=[1,2,2,3,3,4,4,5,5,6]
f1=[2,2,3,3,3,3,4,4,4,5]; fm=[2,2,2,3,3,3,3,3,3,4]
cb0=np.array([[0,1]+b1,[5,2]+bm,[6,1]+bm,[5,2]+bm,[0,1]+b1])
cf=np.array([[0,1]+f1,[5,1]+fm,[5,1]+fm,[5,1]+fm,[0,1]+f1])
syms=[s for s in range(NSYM) if s!=S]   # never touch scatter counts -> trigger odds stay put... (lengths may move)

def single_moves(c):
    for r in range(5):
        for a in syms:
            d=c.copy(); d[r,a]+=1; yield d
            d=c.copy(); d[r,a]-=1; yield d
            for b in syms:
                if a!=b:
                    d=c.copy(); d[r,a]-=1; d[r,b]+=1; yield d

def tune(start, tgt, steps=40, lam=2e-6):
    def loss(c): return abs(analytic(c,cf)['rtp']-tgt) + lam*np.abs(c-cb0).sum()
    cur, lc = start, loss(start)
    for _ in range(steps):
        cands=[(loss(d),i,d) for i,d in enumerate(single_moves(cur)) if valid(d)]
        l,_,d=min(cands,key=lambda x:x[0])
        if l>=lc: 
            # try best pair of moves (2-step lookahead on top-30)
            cands.sort(key=lambda x:x[0]); improved=False
            for _,_,d1 in cands[:30]:
                for d2 in single_moves(d1):
                    if valid(d2):
                        l2=loss(d2)
                        if l2<lc: cur,lc,improved=d2,l2,True; break
                if improved: break
            if not improved: break
        else: cur,lc=d,l
    return cur

out={}
for tgt in (0.96,0.94,0.92):
    c=tune(cb0,tgt, steps=60)
    a=analytic(c,cf)
    out[str(round(tgt*100))]=c
    print(tgt, a['rtp'], a['rtp']-tgt, 'cells changed vs master-start:', int(np.abs(c-cb0).sum()), 'lens', c.sum(1), '1/trig', 1/a['p_trigger'])
    for st in build_strips(c): assert scatter_ok(st)
for st in build_strips(cf): assert scatter_ok(st)
json.dump({"fs_counts":cf.tolist(),"base_counts":{k:v.tolist() for k,v in out.items()}},open("counts.json","w"),indent=1)
for k,v in out.items(): print(k); print(v)
