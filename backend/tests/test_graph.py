"""M3 · 先修图工具（闭包/拓扑）与剩余分支测试。"""
import pytest

from app.core.errors import PrereqCycle
from app.services import graph
from app.services.capacity import normalize_availability


# ---------------- 闭包
def test_prereq_closure_chain():
    edges = [(1, 2), (2, 3)]
    assert graph.prereq_closure(edges, [3]) == {1, 2, 3}


def test_prereq_closure_diamond():
    edges = [(1, 3), (2, 3)]
    assert graph.prereq_closure(edges, [3]) == {1, 2, 3}


def test_prereq_closure_ignores_successors():
    edges = [(1, 2), (2, 3)]
    assert graph.prereq_closure(edges, [2]) == {1, 2}


def test_prereq_closure_multiple_targets():
    edges = [(1, 2), (3, 4)]
    assert graph.prereq_closure(edges, [2, 4]) == {1, 2, 3, 4}


def test_prereq_closure_handles_cycle_without_hanging():
    edges = [(1, 2), (2, 1)]
    assert graph.prereq_closure(edges, [2]) == {1, 2}


# ---------------- 拓扑
def test_topo_order_respects_edges():
    edges = [(1, 2), (2, 3)]
    assert graph.topo_order(edges, [1, 2, 3]) == [1, 2, 3]


def test_topo_order_is_stable_by_id():
    edges = []
    assert graph.topo_order(edges, [5, 3, 1]) == [1, 3, 5]


def test_topo_order_breaks_ties_ascending():
    edges = [(1, 3)]
    assert graph.topo_order(edges, [1, 2, 3]) == [1, 2, 3]


def test_topo_order_ignores_edges_outside_node_set():
    edges = [(9, 10)]
    assert graph.topo_order(edges, [1, 2]) == [1, 2]


def test_topo_order_raises_on_cycle():
    with pytest.raises(PrereqCycle) as e:
        graph.topo_order([(1, 2), (2, 1)], [1, 2])
    assert e.value.code == "E2001"
    assert e.value.detail["cycle"]


def test_ancestors_of():
    edges = [(1, 2), (2, 3)]
    assert graph.ancestors_of(edges, 3) == {1, 2}
    assert graph.ancestors_of(edges, 1) == set()


# ---------------- 库内读取
def test_load_edges_and_concepts(seeded):
    conn = seeded.connect()
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,1,2)")
    conn.commit()
    conn.close()
    assert graph.load_edges(seeded, 1) == [(1, 2)]
    assert len(graph.load_concepts(seeded, 1)) == 3


def test_load_concepts_can_include_disabled(seeded):
    conn = seeded.connect()
    conn.execute("UPDATE concept SET status='disabled' WHERE concept_id=3")
    conn.commit()
    conn.close()
    assert len(graph.load_concepts(seeded, 1)) == 2
    assert len(graph.load_concepts(seeded, 1, only_enabled=False)) == 3


# ---------------- 容量剩余分支
def test_weekday_index_out_of_range():
    with pytest.raises(Exception):
        normalize_availability({"7": [["19:00", "21:00"]]})


def test_default_base_time_used(client):
    """不传 base_time 时用服务端当前时间，不报错。"""
    h = client.post("/api/auth/login",
                    json={"username": "alice", "password": "Passw0rd!"}
                    ).json()["data"]
    headers = {"Authorization": "Bearer " + h["token"]}
    pid = client.post("/api/plans", headers=headers,
                      json={"course_id": 1}).json()["data"]["plan_id"]
    r = client.post("/api/plans/%d/capacity/preview" % pid, headers=headers,
                    json={"target_concept_id": 1, "deadline": "2027-01-31",
                          "availability": {"mon": [["19:00", "21:00"]]}})
    assert r.status_code == 200
    assert r.json()["data"]["C"] >= 0
