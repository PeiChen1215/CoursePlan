"""先修图工具：闭包与稳定拓扑排序（D06 §7.6.2、§7.6.4 的公共部分）。"""
from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .content import detect_cycle


def load_edges(db, course_id: int) -> List[Tuple[int, int]]:
    rows = db.query("SELECT from_concept_id, to_concept_id FROM prerequisite"
                    " WHERE course_id = ?", (course_id,))
    return [(int(r["from_concept_id"]), int(r["to_concept_id"])) for r in rows]


def load_concepts(db, course_id: int, only_enabled: bool = True) -> List[sqlite3.Row]:
    sql = ("SELECT concept_id, name, chapter, difficulty, reference_minutes, status"
           " FROM concept WHERE course_id = ?")
    if only_enabled:
        sql += " AND status = 'enabled'"
    return db.query(sql + " ORDER BY concept_id", (course_id,))


def prereq_closure(edges: Iterable[Tuple[int, int]], targets: Iterable[int]) -> Set[int]:
    """反向收集：目标及其全部先修（含间接）。"""
    parents: Dict[int, Set[int]] = defaultdict(set)
    for u, v in edges:
        parents[v].add(u)
    seen: Set[int] = set()
    stack = list(targets)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(parents.get(node, ()))
    return seen


def topo_order(edges: Iterable[Tuple[int, int]], nodes: Iterable[int]) -> List[int]:
    """稳定拓扑排序：同层按编号升序出队；有环时抛 PrereqCycle。"""
    from ..core.errors import PrereqCycle

    node_list = sorted(nodes)
    indeg: Dict[int, int] = {n: 0 for n in node_list}
    children: Dict[int, List[int]] = defaultdict(list)
    for u, v in edges:
        if u in indeg and v in indeg:
            children[u].append(v)
            indeg[v] += 1

    ready = deque(sorted(n for n, d in indeg.items() if d == 0))
    order: List[int] = []
    while ready:
        node = ready.popleft()
        order.append(node)
        newly = []
        for child in sorted(children.get(node, ())):
            indeg[child] -= 1
            if indeg[child] == 0:
                newly.append(child)
        for n in sorted(newly):
            ready.append(n)

    if len(order) != len(node_list):
        cycle = detect_cycle(edges, node_list)
        raise PrereqCycle("E2001", "先修关系成环", detail={"cycle": cycle})
    return order


def ancestors_of(edges: Sequence[Tuple[int, int]], node: int) -> Set[int]:
    return prereq_closure(edges, [node]) - {node}
