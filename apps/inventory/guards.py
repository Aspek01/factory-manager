# apps/inventory/guards.py
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import connection


@dataclass(frozen=True)
class BomEdge:
    parent_part_id: UUID
    component_part_id: UUID


MAX_BOM_DEPTH = 10  # LOCKED (spec)


def _load_edges(company_id: UUID) -> list[BomEdge]:
    """
    Read BOM graph without importing models (prevents circular imports).
    Uses locked table names:
      inventory_boms, inventory_bom_items
    """
    sql = """
        SELECT b.parent_part_id, i.component_part_id
        FROM inventory_boms b
        JOIN inventory_bom_items i ON i.bom_id = b.id
        WHERE b.company_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql, [str(company_id)])
        rows = cur.fetchall()

    edges: list[BomEdge] = []
    for parent_id, comp_id in rows:
        edges.append(BomEdge(parent_part_id=parent_id, component_part_id=comp_id))
    return edges


def assert_no_circular_bom(company_id: UUID, root_parent_part_id: UUID) -> None:
    """
    Fail-fast if any cycle is reachable from root parent.
    """
    edges = _load_edges(company_id)
    graph: dict[UUID, list[UUID]] = defaultdict(list)
    for e in edges:
        graph[e.parent_part_id].append(e.component_part_id)

    # DFS with colors
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[UUID, int] = defaultdict(int)

    def dfs(node: UUID):
        color[node] = GRAY
        for nxt in graph.get(node, []):
            if color[nxt] == GRAY:
                raise ValidationError("Circular BOM detected")
            if color[nxt] == WHITE:
                dfs(nxt)
        color[node] = BLACK

    dfs(root_parent_part_id)


def assert_max_depth(company_id: UUID, root_parent_part_id: UUID) -> None:
    """
    Fail-fast if BOM depth exceeds MAX_BOM_DEPTH from root.
    """
    edges = _load_edges(company_id)
    graph: dict[UUID, list[UUID]] = defaultdict(list)
    for e in edges:
        graph[e.parent_part_id].append(e.component_part_id)

    q = deque([(root_parent_part_id, 0)])
    visited_depth: dict[UUID, int] = {root_parent_part_id: 0}

    while q:
        node, depth = q.popleft()
        if depth > MAX_BOM_DEPTH:
            raise ValidationError(f"BOM max depth exceeded (>{MAX_BOM_DEPTH})")

        for nxt in graph.get(node, []):
            nd = depth + 1
            # Keep minimal depth; still safe for exceeding check.
            if nxt not in visited_depth or nd < visited_depth[nxt]:
                visited_depth[nxt] = nd
                q.append((nxt, nd))
