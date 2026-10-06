"""Owned finite-object pilot: no JVM payloads and no target applications."""
import itertools,json,time
from runtime_resources import self_peak_rss_kib
from pathlib import Path
# State: per-object (phase-ready bit, value bit, next object or -1).
# A safe object is ready, its bit is 1, and a non-null next object's bit is 1.
def reach(h, roots):
 out=set(); todo=list(roots)
 while todo:
  o=todo.pop()
  if o in out: continue
  out.add(o)
  if h[o][2]>=0: todo.append(h[o][2])
 return out

def inv(h,o):
 r={(o,0)}
 if not h[o][0]: return False,r
 r.add((o,1))
 if not h[o][1]: return False,r
 r.add((o,2)); p=h[o][2]
 if p<0:return True,r
 r.add((p,1)); return bool(h[p][1]),r

def oracle(h, roots):
 # Independent dense transitive closure, eagerly evaluated policy.
 n=len(h); m=[[i==j or h[i][2]==j for j in range(n)] for i in range(n)]
 for k in range(n):
  for i in range(n):
   for j in range(n): m[i][j]=m[i][j] or (m[i][k] and m[k][j])
 live={j for j in range(n) if any(m[i][j] for i in roots)}
 good=all(h[o][0]==1 and h[o][1]==1 and (h[o][2]<0 or h[h[o][2]][1]==1) for o in live)
 return good,live

def run(n, path):
 t=time.process_time(); wall=time.perf_counter(); cnt=dict(states=0,transitions=0,safe_preconditions=0,frontier_mismatches=0,stale_false_accepts=0,full_evaluations=0,incremental_evaluations=0)
 examples={}; domain=list(itertools.product((0,1),(0,1),range(-1,n)))
 for hs in itertools.product(domain,repeat=n):
  for mask in range(1<<n):
   roots={o for o in range(n) if mask>>o&1}
   cnt['states']+=1
   good,oldR=oracle(hs,roots)
   if not good: continue
   cache={o:inv(hs,o)[1] for o in oldR}
   for obj in range(n):
    for f,vals in enumerate(((0,1),(0,1),range(-1,n))):
     for v in vals:
      if v==hs[obj][f]:continue
      h=[list(x) for x in hs];h[obj][f]=v
      for add in (-1,*range(n)):
       newroots=roots|({add} if add>=0 else set())
       cnt['transitions']+=1;cnt['safe_preconditions']+=1
       truth,newR=oracle(h,newroots)
       frontier=(newR-oldR)|{o for o in newR&oldR if (obj,f) in cache[o]}
       result=all(inv(h,o)[0] for o in frontier)
       cnt['full_evaluations']+=len(newR);cnt['incremental_evaluations']+=len(frontier)
       if result!=truth:
        cnt['frontier_mismatches']+=1
        examples.setdefault('frontier_error',dict(before=hs,roots=sorted(roots),write=[obj,f,v],add=add,frontier=sorted(frontier),truth=truth))
       naive=all(inv(h,o)[0] for o in newR-oldR)
       if naive and not truth:
        cnt['stale_false_accepts']+=1
        examples.setdefault('stale_cache',dict(before=hs,roots=sorted(roots),write=[obj,f,v],add=add,after=h,truth=truth))
 out=dict(n=n,counts=cnt,examples=examples,cpu_seconds=time.process_time()-t,wall_seconds=time.perf_counter()-wall,peak_rss_kib=self_peak_rss_kib())
 Path(path).write_text(json.dumps(out,indent=2)+'\n')

 assert cnt['frontier_mismatches']==0 and cnt['stale_false_accepts']>0
 return out
