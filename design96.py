import numpy as np, json, time
from game import analytic
from greedy import greedy
TARGET = dict(rtp=0.96, line_base=0.66, scatter_base=0.035, p_trigger=1/125, fs_value=33.0)
def loss(cb, cf):
    a = analytic(cb, cf)
    return (((a["rtp"]-TARGET["rtp"])/0.0002)**2 + ((a["line_base"]-TARGET["line_base"])/0.01)**2
            + ((a["scatter_base"]-TARGET["scatter_base"])/0.005)**2 + ((a["p_trigger"]-TARGET["p_trigger"])/0.0005)**2
            + ((a["fs_value"]-TARGET["fs_value"])/2.0)**2)
cb = np.array([[0,1,2,2,3,3,4,4,5,5,5,6],[3,1,2,2,3,3,4,4,4,4,5,5],[3,1,2,2,3,3,4,4,4,4,5,5],
               [3,1,2,2,3,3,4,4,4,4,5,5],[0,1,2,2,3,3,4,4,5,5,5,6]])
cf = np.array([[0,1,2,3,3,3,3,4,4,4,4,5],[6,1,2,2,3,3,3,3,3,3,3,4],[6,1,2,2,3,3,3,3,3,3,3,4],
               [6,1,2,2,3,3,3,3,3,3,3,4],[0,1,2,3,3,3,3,4,4,4,4,5]])
t=time.time(); loss(cb,cf); print("eval ms", (time.time()-t)*1000)
cb, cf, l = greedy(cb, cf, loss, verbose=True, max_steps=150)
a = analytic(cb, cf)
print(l, {k: float(v) for k, v in a.items() if np.ndim(v)==0})
print(cb); print(cf)
json.dump({"cb": cb.tolist(), "cf": cf.tolist()}, open("master96.json","w"))
