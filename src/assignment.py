"""Rectangular Hungarian assignment for live track matching and Tap selection."""
from __future__ import annotations
import math


def assign(costs: list[list[float]]) -> list[tuple[int,int]]:
    """Return minimum-cost row/column pairs, with one column per row (m >= n)."""
    if not costs:
        return []
    n,m = len(costs),len(costs[0])
    if m < n or any(len(row)!=m for row in costs) or any(not math.isfinite(x) for row in costs for x in row):
        raise ValueError("Expected a finite rectangular cost matrix with columns >= rows")
    u,v,p,way = [0.0]*(n+1),[0.0]*(m+1),[0]*(m+1),[0]*(m+1)
    for i in range(1,n+1):
        p[0],j0 = i,0
        minimum,used = [float("inf")]* (m+1),[False]*(m+1)
        while True:
            used[j0] = True
            i0,delta,j1 = p[j0],float("inf"),0
            for j in range(1,m+1):
                if not used[j]:
                    reduced = costs[i0-1][j-1]-u[i0]-v[j]
                    if reduced < minimum[j]:
                        minimum[j],way[j] = reduced,j0
                    if minimum[j] < delta:
                        delta,j1 = minimum[j],j
            for j in range(m+1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return sorted((p[j]-1,j-1) for j in range(1,m+1) if p[j])
