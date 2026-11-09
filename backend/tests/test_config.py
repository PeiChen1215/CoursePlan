"""M1 · config 模块单元测试（对应 D06 §14.6.1 / §14.6.2）。"""
import pytest

from app.core import config as C


def test_defaults_equal_d06_table_2_2():
    cfg = C.load({})
    expected = {
        "STUDY_RATIO": 0.70, "BUFFER_RATIO": 0.10, "MAX_SLICE_SECONDS": 7200,
        "MAX_SLICES_PER_TASK": 100, "CAP_TIGHT_THRESHOLD": 0.80,
        "DELAY_THRESHOLD_HOURS": 48, "MODEL_TIMEOUT_SECONDS": 10,
        "MIN_TASK_MINUTES": 1, "MAX_DEADLINE_DAYS": 180,
        "LOCK_FAIL_LIMIT": 5, "LOCK_MINUTES": 5, "TOKEN_TTL_HOURS": 24,
    }
    for k, v in expected.items():
        assert getattr(cfg, k) == v, k


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("DSH_BUFFER_RATIO", "0.2")
    assert C.load({}).BUFFER_RATIO == 0.2


def test_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("DSH_STUDY_RATIO", "0.8")
    assert C.load({"STUDY_RATIO": 0.55}).STUDY_RATIO == 0.55


def test_int_config_coerced_from_env(monkeypatch):
    monkeypatch.setenv("DSH_MAX_SLICES_PER_TASK", "42")
    v = C.load({}).MAX_SLICES_PER_TASK
    assert v == 42 and isinstance(v, int)


@pytest.mark.parametrize("key,value", [
    ("STUDY_RATIO", 0.95), ("STUDY_RATIO", 0.05),
    ("BUFFER_RATIO", -0.1), ("BUFFER_RATIO", 0.6),
    ("MAX_SLICES_PER_TASK", 0), ("MAX_SLICES_PER_TASK", 501),
    ("MODEL_TIMEOUT_SECONDS", 0), ("MODEL_TIMEOUT_SECONDS", 61),
    ("MAX_DEADLINE_DAYS", 3), ("MAX_DEADLINE_DAYS", 400),
    ("TOKEN_TTL_HOURS", 0), ("TOKEN_TTL_HOURS", 100),
])
def test_out_of_range_rejected_with_key_name(key, value):
    with pytest.raises(C.ConfigError) as e:
        C.load({key: value})
    assert key in str(e.value)


def test_non_numeric_rejected():
    with pytest.raises(C.ConfigError):
        C.load({"MAX_SLICES_PER_TASK": "abc"})


def test_bad_choice_rejected():
    with pytest.raises(C.ConfigError) as e:
        C.load({"PROVIDER_MODE": "gpt"})
    assert "PROVIDER_MODE" in str(e.value)
    with pytest.raises(C.ConfigError):
        C.load({"LOG_LEVEL": "VERBOSE"})


def test_db_file_relative_resolved_under_project_root():
    cfg = C.load({"DB_PATH": "data/x.db"})
    assert cfg.db_file.is_absolute()
    assert cfg.db_file.as_posix().endswith("data/x.db")
    assert cfg.db_file.parents[1].name == "CoursePlan"


def test_db_file_absolute_kept(tmp_path):
    p = tmp_path / "a.db"
    assert C.load({"DB_PATH": str(p)}).db_file == p


def test_as_dict_has_no_secrets():
    d = C.load({}).as_dict()
    assert "SECRET_KEY" not in d and "PROVIDER_KEY" not in d
    assert d["MAX_SLICES_PER_TASK"] == 100


def test_frozen_config_cannot_be_mutated():
    cfg = C.load({})
    with pytest.raises(Exception):
        cfg.STUDY_RATIO = 0.5


def test_backup_dir_relative_to_db_file():
    """相对路径落在数据库同级目录下，便于整目录搬走。"""
    cfg = C.EngineConfig(**{**C.DEFAULTS, "DB_PATH": "data/x.db"})
    assert cfg.backup_dir == cfg.db_file.parent / "backups"


def test_backup_dir_absolute_is_honoured(tmp_path):
    cfg = C.EngineConfig(**{**C.DEFAULTS, "DB_PATH": "data/x.db",
                        "BACKUP_DIR": str(tmp_path / "bk")})
    assert cfg.backup_dir == tmp_path / "bk"
