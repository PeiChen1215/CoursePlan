"""资源维护与关联（D02 F-05 / AT-09 / AT-10）。"""
import pytest

from app.core.errors import NotFound, ValidationError
from app.services.resource import ResourceInput, ResourceService


def token_of(client, username="alice"):
    pwd = "Passw0rd!" if username == "alice" else "Admin123!"
    data = client.post("/api/auth/login",
                       json={"username": username, "password": pwd}).json()["data"]
    return data["token"]


def auth(token):
    return {"Authorization": "Bearer " + token}


def svc(client):
    return ResourceService(client.app.state.db)


def test_create_requires_url_or_summary(client):
    with pytest.raises(ValidationError) as e:
        svc(client).create_resource(1, ResourceInput(title="空资料", type="document"))
    assert e.value.field == "url"


def test_create_link_requires_url(client):
    with pytest.raises(ValidationError):
        svc(client).create_resource(1, ResourceInput(title="链接", type="link"))


def test_create_rejects_bad_url(client):
    with pytest.raises(ValidationError) as e:
        svc(client).create_resource(
            1, ResourceInput(title="外部", type="link", url="ftp://x"))
    assert e.value.field == "url"


def test_create_rejects_bad_type(client):
    with pytest.raises(ValidationError) as e:
        svc(client).create_resource(
            1, ResourceInput(title="怪", type="podcast", summary="s"))
    assert e.value.field == "type"


def test_create_rejects_long_title_and_minutes(client):
    with pytest.raises(ValidationError):
        svc(client).create_resource(
            1, ResourceInput(title="x" * 201, type="document", summary="s"))
    with pytest.raises(ValidationError):
        svc(client).create_resource(
            1, ResourceInput(title="ok", type="document", summary="s", read_minutes=241))


def test_create_on_missing_course_404(client):
    with pytest.raises(NotFound):
        svc(client).create_resource(
            99, ResourceInput(title="ok", type="document", summary="s"))


def test_create_and_list(client):
    rid = svc(client).create_resource(
        1, ResourceInput(title="需求工程速览", type="document",
                         url="https://example.com/re", read_minutes=20))
    items = svc(client).list_resources(1)
    row = [i for i in items if i["resource_id"] == rid][0]
    assert row["title"] == "需求工程速览" and row["status"] == "enabled"
    assert row["type_label"] == "文档"


def test_disable_resource_counts_links(client):
    service = svc(client)
    rid = service.create_resource(1, ResourceInput(title="R", type="document", summary="s"))
    service.set_concept_resources(1, [rid])
    out = service.disable_resource(rid)
    assert out["linked_concepts"] == 1
    row = [i for i in service.list_resources(1) if i["resource_id"] == rid][0]
    assert row["status"] == "disabled"


def test_disable_missing_resource(client):
    with pytest.raises(NotFound):
        svc(client).disable_resource(999)


def test_set_concept_resources_replaces(client):
    service = svc(client)
    a = service.create_resource(1, ResourceInput(title="A", type="document", summary="s"))
    b = service.create_resource(1, ResourceInput(title="B", type="document", summary="s"))
    service.set_concept_resources(1, [a, b])
    assert len(service.concept_resources(1)) == 2
    service.set_concept_resources(1, [b])
    assert [r["resource_id"] for r in service.concept_resources(1)] == [b]


def test_set_concept_resources_rejects_unknown_resource(client):
    """单课程产品（ux_single_course），跨课程资源不可能存在；这里验未登记的资源被拒。"""
    service = svc(client)
    service.create_resource(1, ResourceInput(title="X", type="document", summary="s"))
    with pytest.raises(ValidationError) as e:
        service.set_concept_resources(1, [999])
    assert e.value.field == "resource_ids"
    assert service.concept_resources(1) == []


def test_set_concept_resources_missing_concept(client):
    with pytest.raises(NotFound):
        svc(client).set_concept_resources(999, [])


def test_resources_for_tasks_groups_enabled_only(client):
    service = svc(client)
    a = service.create_resource(1, ResourceInput(title="A", type="document", summary="s"))
    b = service.create_resource(1, ResourceInput(title="B", type="document", summary="s"))
    service.set_concept_resources(1, [a, b])
    service.disable_resource(b)
    grouped = service.resources_for_tasks([1, 2])
    assert [r["resource_id"] for r in grouped[1]] == [a]
    assert grouped.get(2) is None
    assert service.resources_for_tasks([]) == {}


def test_http_resource_flow(client):
    h_admin = auth(token_of(client, "admin"))
    h = auth(token_of(client))
    created = client.post("/api/courses/1/resources", headers=h_admin, json={
        "title": "用例图讲解", "type": "video",
        "url": "https://example.com/uc", "read_minutes": 15}).json()["data"]
    rid = created["resource_id"]
    items = client.get("/api/courses/1/resources", headers=h).json()["data"]["items"]
    assert any(i["resource_id"] == rid for i in items)

    client.put("/api/concepts/1/resources", headers=h_admin,
               json={"resource_ids": [rid]})
    linked = client.get("/api/concepts/1/resources", headers=h).json()["data"]["items"]
    assert [i["resource_id"] for i in linked] == [rid]

    assert client.post("/api/resources/%d/disable" % rid,
                       headers=h_admin).json()["data"]["linked_concepts"] == 1


def test_student_cannot_write_resources(client):
    h = auth(token_of(client))
    assert client.post("/api/courses/1/resources", headers=h, json={
        "title": "x", "type": "document", "summary": "s"}).status_code == 403
    assert client.put("/api/concepts/1/resources", headers=h,
                      json={"resource_ids": []}).status_code == 403
    assert client.post("/api/resources/1/disable", headers=h).status_code == 403

def test_create_rejects_long_url(client):
    with pytest.raises(ValidationError) as e:
        svc(client).create_resource(
            1, ResourceInput(title="长", type="link", url="https://x/" + "a" * 2100))
    assert e.value.field == "url"

def test_list_resources_can_skip_disabled(client):
    service = svc(client)
    alive = service.create_resource(1, ResourceInput(title="在", type="document", summary="s"))
    gone = service.create_resource(1, ResourceInput(title="停", type="document", summary="s"))
    service.disable_resource(gone)
    ids = [r["resource_id"] for r in service.list_resources(1, include_disabled=False)]
    assert ids == [alive]

def test_resources_for_tasks_dedupes(client):
    service = svc(client)
    a = service.create_resource(1, ResourceInput(title="A", type="document", summary="s"))
    service.set_concept_resources(1, [a, a])
    grouped = service.resources_for_tasks([1, 1])
    assert len(grouped[1]) == 1

def test_link_type_with_summary_still_requires_url(client):
    """有摘要但没有网址的 link 也要拒绝（schema 同样要求）。"""
    with pytest.raises(ValidationError) as e:
        svc(client).create_resource(1, ResourceInput(title="只能是链接", type="link",
                                                        summary="说明"))
    assert e.value.field == "url"
