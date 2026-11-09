"""一致性备份与恢复（D02 AT-31）。"""
import sqlite3
from pathlib import Path

import pytest

from app.core.errors import NotFound, ValidationError
from app.services.backup import BackupError, BackupService


def token_of(client, username="admin"):
    pwd = "Admin123!" if username == "admin" else "Passw0rd!"
    data = client.post("/api/auth/login",
                       json={"username": username, "password": pwd}).json()["data"]
    return data["token"]


def auth(token):
    return {"Authorization": "Bearer " + token}


def service(client, keep=7):
    db_file = client.app.state.config.db_file
    return BackupService(db_file, Path(db_file).parent / "backups", keep)


def test_backup_creates_consistent_copy(client):
    svc = service(client)
    result = svc.backup()
    assert result.integrity == "ok"
    assert result.foreign_key_violations == 0
    assert Path(result.path).exists() and result.size_bytes > 0
    conn = sqlite3.connect(result.path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM app_user").fetchone()[0] >= 2
    finally:
        conn.close()


def test_backup_requires_existing_db(tmp_path):
    svc = BackupService(tmp_path / "missing.db", tmp_path / "backups")
    with pytest.raises(BackupError):
        svc.backup()


def test_backup_prunes_to_keep(client):
    svc = service(client, keep=2)
    for _ in range(4):
        svc.backup()
    names = [Path(r["name"]).name for r in svc.list_backups()]
    assert len(names) == 2


def test_list_backups_newest_first(client):
    svc = service(client, keep=5)
    svc.backup()
    items = svc.list_backups()
    assert items and items[0]["created_at"] >= items[-1]["created_at"]
    assert items[0]["size_bytes"] > 0


def test_list_backups_empty_dir(tmp_path):
    svc = BackupService(tmp_path / "x.db", tmp_path / "none")
    assert svc.list_backups() == []
    assert svc.latest() is None


def test_restore_roundtrip(client):
    svc = service(client)
    result = svc.backup()
    name = Path(result.path).name
    before = client.app.state.db.query("SELECT COUNT(*) AS n FROM concept")[0]["n"]
    from app.db.uow import UnitOfWork
    with UnitOfWork(client.app.state.db) as uow:
        uow.execute("DELETE FROM concept_resource")
    restored = svc.restore(name)
    assert restored["integrity"] == "ok"
    assert restored["counts"]["concept"] == before
    assert Path(restored["safeguard"]).exists()


def test_restore_missing_backup(client):
    with pytest.raises(NotFound):
        service(client).restore("nope.db")


def test_restore_rejects_corrupt_backup(client):
    svc = service(client)
    svc.backup()
    bad = Path(svc.backup_dir) / "studypath-broken.db"
    bad.write_bytes(b"not a database")
    assert svc._integrity(bad) == "corrupt"
    with pytest.raises(ValidationError):
        svc.restore(bad.name)


def test_http_backup_and_list(client):
    h = auth(token_of(client))
    created = client.post("/api/admin/backup", headers=h).json()["data"]
    assert created["integrity"] == "ok"
    items = client.get("/api/admin/backups", headers=h).json()["data"]["items"]
    assert items and items[0]["name"].startswith("studypath-")


def test_http_restore(client):
    h = auth(token_of(client))
    created = client.post("/api/admin/backup", headers=h).json()["data"]
    out = client.post("/api/admin/restore", headers=h,
                      json={"name": created["name"]}).json()["data"]
    assert out["integrity"] == "ok" and out["counts"]["course"] >= 1


def test_student_cannot_backup(client):
    h = auth(token_of(client, "alice"))
    assert client.post("/api/admin/backup", headers=h).status_code == 403
    assert client.get("/api/admin/backups", headers=h).status_code == 403
    assert client.post("/api/admin/restore", headers=h,
                       json={"name": "x.db"}).status_code == 403

def test_integrity_handles_corrupt_file(client):
    bad = Path(service(client).backup_dir) / "studypath-corrupt2.db"
    service(client).backup_dir.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"broken")
    svc = service(client)
    assert svc._integrity(bad) == "corrupt"
    assert svc._foreign_key_violations(bad) == 1

def test_restore_rejects_foreign_key_violation(client):
    from app.core.errors import ValidationError as VE
    svc = service(client)
    result = svc.backup()
    conn = sqlite3.connect(result.path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("INSERT INTO concept_resource(concept_id,resource_id,course_id)"
                     " VALUES(999,999,1)")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(VE):
        svc.restore(Path(result.path).name)

def test_restore_removes_wal_sidecars(client):
    svc = service(client)
    result = svc.backup()
    side = Path(str(client.app.state.config.db_file) + "-wal")
    side.write_bytes(b"")
    svc.restore(Path(result.path).name)
    assert not side.exists()

def test_dedupe_removed_from_resources(client):
    """concept_resource 主键保证唯一，分组结果不会重复。"""
    from app.services.resource import ResourceInput, ResourceService
    rs = ResourceService(client.app.state.db)
    rid = rs.create_resource(1, ResourceInput(title="Z", type="document", summary="s"))
    rs.set_concept_resources(1, [rid, rid])
    assert len(rs.resources_for_tasks([1])[1]) == 1
