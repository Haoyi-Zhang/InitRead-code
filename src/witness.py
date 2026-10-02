"""Exact, finite, ordered witness pilot. No gadget or target-program search.

Only locally authored JSON transition systems are accepted by this experiment.
The alphabet is the fixed list of four-integer heap events, ordered by edge id.
"""
from collections import deque
from model import successor, evaluate, reachable
from oracle import exact

def bfs(program, cap=8192, key_mode="semantic"):
    heap=tuple(tuple(row) for row in program["heap"])
    roots=frozenset(program["roots"])
    edges={}
    for edge in program["edges"]:
        edges.setdefault(edge["from"], []).append(edge)
    for row in edges.values():
        row.sort(key=lambda e:e["order"])
        if len({e["order"] for e in row}) != len(row):
            raise ValueError("outgoing order identifiers must be unique")
    def key(pc,h,r,epoch):
        if key_mode=="semantic": return pc,h,r
        if key_mode=="erase-ready": return pc,tuple(row[1:] for row in h),r
        if key_mode=="retain-epoch": return pc,h,r,epoch
        raise ValueError("unknown key mode")
    if not all(evaluate(heap,o)[0] for o in reachable(heap, roots)):
        return {"status":"VIOLATION","trace":[],"visited":1,"transitions":0}
    queue=deque([(program["start"],heap,roots,0,[])])
    seen={key(program["start"],heap,roots,0)}
    transitions=0
    while queue:
        pc,h,r,epoch,path=queue.popleft()
        for edge in edges.get(pc, []):
            nh,nr=successor(h,r,tuple(edge["event"]))
            transitions+=1
            np=path+[edge["order"]]
            if not all(evaluate(nh,o)[0] for o in reachable(nh,nr)):
                return {"status":"VIOLATION","trace":np,"visited":len(seen),"transitions":transitions}
            nk=key(edge["to"],nh,nr,epoch+1)
            if nk not in seen:
                if len(seen)>=cap:
                    return {"status":"UNKNOWN","trace":None,"visited":len(seen),"transitions":transitions}
                seen.add(nk); queue.append((edge["to"],nh,nr,epoch+1,np))
    return {"status":"SAFE","trace":None,"visited":len(seen),"transitions":transitions}

def enumerated_oracle(program, max_depth=8, cap=100000):
    """No state quotient: enumerate whole paths in length/lexicographic order.

    'NO_WITNESS_TO_DEPTH' is not a proof of safety for a looping program.
    """
    initial=(program["start"],tuple(tuple(x) for x in program["heap"]),frozenset(program["roots"]),[])
    if not exact(initial[1], initial[2])[0]:
        return {"status":"VIOLATION","trace":[],"transitions":0}
    layer=[initial]; tested=0
    for depth in range(max_depth):
        following=[]
        for pc,h,roots,path in sorted(layer,key=lambda s:s[3]):
            for edge in sorted([e for e in program["edges"] if e["from"]==pc],key=lambda e:e["order"]):
                # Separate eager update implementation; no producer successor call.
                obj,field,val,add=edge["event"]
                nh=[list(x) for x in h]; nh[obj][field]=val; nh=tuple(tuple(x) for x in nh)
                nr=roots | ({add} if add>=0 else set())
                candidate=path+[edge["order"]];tested+=1
                if tested>cap:
                    return {"status":"UNKNOWN","trace":None,"transitions":tested}
                if not exact(nh,nr)[0]:
                    return {"status":"VIOLATION","trace":candidate,"transitions":tested}
                following.append((edge["to"],nh,frozenset(nr),candidate))
        if not following:
            return {"status":"SAFE","trace":None,"transitions":tested}
        layer=following
    return {"status":"NO_WITNESS_TO_DEPTH","trace":None,"transitions":tested}
