"""Bounded aggregate route diagnostics; never store text or identifiers."""
from collections import defaultdict
from time import monotonic

class RouteDiagnostics:
    def __init__(self,clock=monotonic):
        self.clock=clock
        self.rows=defaultdict(lambda:{"count":0,"total_ms":0,"max_ms":0})
    def record(self,route,status,started):
        elapsed=max(0,round((self.clock()-started)*1000))
        row=self.rows[(route,status)]
        row["count"]+=1
        row["total_ms"]+=elapsed
        row["max_ms"]=max(row["max_ms"],elapsed)
        return elapsed
    def snapshot(self):
        return {route+":"+status:dict(row) for (route,status),row in self.rows.items()}
