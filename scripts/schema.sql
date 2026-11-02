-- =====================================================================
-- 学径 StudyPath —— 课程学习规划辅助系统
-- 数据库：studyplan.db（SQLite 3.35+，需 JSON1 函数）
-- 对应文档：D05 数据库设计说明书 v1.0（§3.2 关系模式、§3.3 索引与触发器、§4.1 数据字典）
-- 设计要点：
--   1) 16 张表：15 张业务与支撑表 + 1 张模式元数据表
--   2) 三表分离：plan_task（稳定身份）/ version_task（版本安排）/ task_slice（时间片）
--   3) 复合外键保证同课程、同计划归属，防止跨课程错配
--   4) 不可变触发器保护已生效版本及其子项；sealed 触发器阻止确认后补写历史
--   5) 时间：审计时间 UTC ISO 8601（Z 结尾）；时间片 UTC Unix 秒且整分钟；业务日期本地 YYYY-MM-DD
-- 说明：全部语句幂等，可重复执行；不替代正式迁移脚本。
-- =====================================================================

PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 3000;

-- ---------------------------------------------------------------- 0 模式元数据
CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY NOT NULL,
  value TEXT NOT NULL
);

-- ---------------------------------------------------------------- 1 用户
CREATE TABLE IF NOT EXISTS app_user (
  user_id         INTEGER PRIMARY KEY,
  username        TEXT    NOT NULL UNIQUE
                  CHECK (length(username) BETWEEN 3 AND 32),
  password_hash   TEXT    NOT NULL,
  role            TEXT    NOT NULL CHECK (role IN ('student', 'admin')),
  status          TEXT    NOT NULL DEFAULT 'enabled'
                  CHECK (status IN ('enabled', 'disabled')),
  failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
  locked_until    TEXT,
  last_login_at   TEXT,
  created_at      TEXT    NOT NULL
);

-- ---------------------------------------------------------------- 2 课程
CREATE TABLE IF NOT EXISTS course (
  course_id        INTEGER PRIMARY KEY,
  maintainer_id    INTEGER NOT NULL
                   REFERENCES app_user(user_id) ON DELETE RESTRICT,
  name             TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  description      TEXT    NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
  semester         TEXT    NOT NULL,
  total_hours      INTEGER NOT NULL CHECK (total_hours > 0),
  status           TEXT    NOT NULL CHECK (status IN ('enabled', 'disabled')),
  content_revision INTEGER NOT NULL DEFAULT 0 CHECK (content_revision >= 0)
);

-- ---------------------------------------------------------------- 3 知识点
CREATE TABLE IF NOT EXISTS concept (
  concept_id        INTEGER PRIMARY KEY,
  course_id         INTEGER NOT NULL,
  name              TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  chapter           TEXT    NOT NULL,
  difficulty        INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
  reference_minutes INTEGER NOT NULL CHECK (reference_minutes BETWEEN 5 AND 600),
  objectives_json   TEXT    NOT NULL DEFAULT '[]'
                    CHECK (json_valid(objectives_json) AND json_type(objectives_json) = 'array'),
  pitfalls_json     TEXT    NOT NULL DEFAULT '[]'
                    CHECK (json_valid(pitfalls_json) AND json_type(pitfalls_json) = 'array'),
  sort_order        INTEGER NOT NULL DEFAULT 1 CHECK (sort_order >= 1),
  status            TEXT    NOT NULL CHECK (status IN ('enabled', 'disabled')),
  UNIQUE (course_id, name),
  UNIQUE (concept_id, course_id),
  FOREIGN KEY (course_id) REFERENCES course(course_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 4 先修关系
CREATE TABLE IF NOT EXISTS prerequisite (
  prereq_id       INTEGER PRIMARY KEY,
  course_id       INTEGER NOT NULL,
  from_concept_id INTEGER NOT NULL,
  to_concept_id   INTEGER NOT NULL,
  CHECK (from_concept_id <> to_concept_id),
  UNIQUE (from_concept_id, to_concept_id),
  FOREIGN KEY (from_concept_id, course_id) REFERENCES concept(concept_id, course_id) ON DELETE RESTRICT,
  FOREIGN KEY (to_concept_id, course_id)   REFERENCES concept(concept_id, course_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 5 资源
CREATE TABLE IF NOT EXISTS resource (
  resource_id  INTEGER PRIMARY KEY,
  course_id    INTEGER NOT NULL,
  title        TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  type         TEXT    NOT NULL CHECK (type IN ('document', 'video', 'exercise', 'link')),
  url          TEXT    CHECK (url IS NULL OR (length(url) <= 2048
                       AND (url LIKE 'http://%' OR url LIKE 'https://%'))),
  summary      TEXT    CHECK (summary IS NULL OR length(summary) <= 2000),
  read_minutes INTEGER NOT NULL DEFAULT 0 CHECK (read_minutes BETWEEN 0 AND 240),
  status       TEXT    NOT NULL CHECK (status IN ('enabled', 'disabled')),
  UNIQUE (resource_id, course_id),
  CHECK (coalesce(length(trim(url)), 0) > 0 OR coalesce(length(trim(summary)), 0) > 0),
  CHECK (type <> 'link' OR url IS NOT NULL),
  FOREIGN KEY (course_id) REFERENCES course(course_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 6 知识点资源关联
CREATE TABLE IF NOT EXISTS concept_resource (
  concept_id  INTEGER NOT NULL,
  resource_id INTEGER NOT NULL,
  course_id   INTEGER NOT NULL,
  PRIMARY KEY (concept_id, resource_id),
  FOREIGN KEY (concept_id, course_id)  REFERENCES concept(concept_id, course_id) ON DELETE RESTRICT,
  FOREIGN KEY (resource_id, course_id) REFERENCES resource(resource_id, course_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 7 学习计划
CREATE TABLE IF NOT EXISTS study_plan (
  plan_id           INTEGER PRIMARY KEY,
  student_id        INTEGER NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
  course_id         INTEGER NOT NULL REFERENCES course(course_id) ON DELETE RESTRICT,
  status            TEXT    NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'active', 'completed', 'archived')),
  current_version   INTEGER CHECK (current_version IS NULL OR current_version >= 1),
  progress_revision INTEGER NOT NULL DEFAULT 0 CHECK (progress_revision >= 0),
  created_at        TEXT    NOT NULL,
  updated_at        TEXT    NOT NULL,
  UNIQUE (plan_id, course_id),
  CHECK (status = 'draft' OR current_version IS NOT NULL),
  FOREIGN KEY (plan_id, current_version)
    REFERENCES plan_version(plan_id, version_no) DEFERRABLE INITIALLY DEFERRED
);

-- ---------------------------------------------------------------- 8 学习约束
CREATE TABLE IF NOT EXISTS plan_constraint (
  constraint_id            INTEGER PRIMARY KEY,
  plan_id                  INTEGER NOT NULL UNIQUE,
  course_id                INTEGER NOT NULL,
  target_concept_id        INTEGER NOT NULL,
  extra_concept_ids_json   TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(extra_concept_ids_json)),
  deadline                 TEXT    NOT NULL,
  availability_json        TEXT    NOT NULL CHECK (json_valid(availability_json)),
  excluded_dates_json      TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(excluded_dates_json)),
  mastered_concept_ids_json TEXT   NOT NULL DEFAULT '[]' CHECK (json_valid(mastered_concept_ids_json)),
  base_time                TEXT    NOT NULL,
  FOREIGN KEY (plan_id, course_id)         REFERENCES study_plan(plan_id, course_id) ON DELETE RESTRICT,
  FOREIGN KEY (target_concept_id, course_id) REFERENCES concept(concept_id, course_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 9 稳定逻辑任务
CREATE TABLE IF NOT EXISTS plan_task (
  task_id    INTEGER PRIMARY KEY,
  plan_id    INTEGER NOT NULL,
  course_id  INTEGER NOT NULL,
  concept_id INTEGER NOT NULL,
  task_type  TEXT    NOT NULL CHECK (task_type IN ('study', 'practice')),
  created_at TEXT    NOT NULL,
  UNIQUE (plan_id, concept_id, task_type),
  UNIQUE (task_id, plan_id),
  FOREIGN KEY (plan_id, course_id)     REFERENCES study_plan(plan_id, course_id) ON DELETE RESTRICT,
  FOREIGN KEY (concept_id, course_id)  REFERENCES concept(concept_id, course_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 10 计划版本（不可变）
CREATE TABLE IF NOT EXISTS plan_version (
  version_id     INTEGER PRIMARY KEY,
  plan_id        INTEGER NOT NULL REFERENCES study_plan(plan_id) ON DELETE RESTRICT,
  version_no     INTEGER NOT NULL CHECK (version_no >= 1),
  change_reason  TEXT    NOT NULL
                 CHECK (change_reason IN ('initial', 'delay', 'goal_change',
                                          'availability_change', 'duration_change', 'manual')),
  change_note    TEXT    NOT NULL CHECK (length(trim(change_note)) BETWEEN 1 AND 500),
  snapshot_json  TEXT    NOT NULL CHECK (json_valid(snapshot_json)),
  input_hash     TEXT    NOT NULL CHECK (length(input_hash) = 64),
  engine_version TEXT    NOT NULL,
  operator_id    INTEGER NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
  created_at     TEXT    NOT NULL,
  UNIQUE (plan_id, version_no),
  UNIQUE (version_id, plan_id)
);

-- ---------------------------------------------------------------- 11 版本任务安排（不可变）
CREATE TABLE IF NOT EXISTS version_task (
  version_id         INTEGER NOT NULL,
  task_id            INTEGER NOT NULL,
  plan_id            INTEGER NOT NULL,
  in_scope           INTEGER NOT NULL CHECK (in_scope IN (0, 1)),
  frozen             INTEGER NOT NULL CHECK (frozen IN (0, 1)),
  original_minutes   INTEGER NOT NULL CHECK (original_minutes BETWEEN 1 AND 1440),
  estimated_minutes  INTEGER NOT NULL CHECK (estimated_minutes BETWEEN 1 AND 1440),
  override_minutes   INTEGER CHECK (override_minutes IS NULL OR override_minutes BETWEEN 1 AND 1440),
  override_note      TEXT,
  schedule_state     TEXT    NOT NULL
                     CHECK (schedule_state IN ('scheduled', 'unscheduled', 'historical')),
  PRIMARY KEY (version_id, task_id),
  UNIQUE (version_id, task_id, plan_id),
  CHECK (override_minutes IS NULL OR estimated_minutes = override_minutes),
  FOREIGN KEY (version_id, plan_id) REFERENCES plan_version(version_id, plan_id) ON DELETE RESTRICT,
  FOREIGN KEY (task_id, plan_id)    REFERENCES plan_task(task_id, plan_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 12 版本任务时间片（不可变）
CREATE TABLE IF NOT EXISTS task_slice (
  slice_id    INTEGER PRIMARY KEY,
  version_id  INTEGER NOT NULL,
  task_id     INTEGER NOT NULL,
  slice_no    INTEGER NOT NULL CHECK (slice_no >= 1),
  start_epoch INTEGER NOT NULL CHECK (start_epoch % 60 = 0),
  end_epoch   INTEGER NOT NULL CHECK (end_epoch % 60 = 0),
  UNIQUE (version_id, task_id, slice_no),
  CHECK (end_epoch > start_epoch AND end_epoch - start_epoch <= 7200),
  FOREIGN KEY (version_id, task_id) REFERENCES version_task(version_id, task_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 13 版本校验报告（不可变）
CREATE TABLE IF NOT EXISTS plan_validation (
  validation_id INTEGER PRIMARY KEY,
  version_id    INTEGER NOT NULL UNIQUE,
  passed        INTEGER NOT NULL CHECK (passed = 1),
  issues_json   TEXT    NOT NULL CHECK (json_valid(issues_json)),
  metrics_json  TEXT    NOT NULL CHECK (json_valid(metrics_json)),
  FOREIGN KEY (version_id) REFERENCES plan_version(version_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 14 学习事件（只追加）
CREATE TABLE IF NOT EXISTS learning_event (
  event_id         INTEGER PRIMARY KEY,
  plan_id          INTEGER NOT NULL,
  task_id          INTEGER NOT NULL,
  version_id       INTEGER NOT NULL,
  event_type       TEXT    NOT NULL CHECK (event_type IN ('done', 'correction', 'note')),
  actual_minutes   INTEGER CHECK (actual_minutes IS NULL OR actual_minutes >= 0),
  note             TEXT    CHECK (note IS NULL OR length(note) <= 500),
  operator_id      INTEGER NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
  request_key      TEXT    NOT NULL UNIQUE,
  corrects_event_id INTEGER REFERENCES learning_event(event_id) ON DELETE RESTRICT,
  occurred_at      TEXT    NOT NULL,
  CHECK ((event_type = 'correction' AND corrects_event_id IS NOT NULL)
      OR (event_type <> 'correction' AND corrects_event_id IS NULL)),
  FOREIGN KEY (version_id, task_id, plan_id)
    REFERENCES version_task(version_id, task_id, plan_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 15 持久化草案
CREATE TABLE IF NOT EXISTS plan_draft (
  draft_id              INTEGER PRIMARY KEY,
  plan_id               INTEGER NOT NULL REFERENCES study_plan(plan_id) ON DELETE RESTRICT,
  revision              INTEGER NOT NULL CHECK (revision >= 1),
  base_version          INTEGER,
  base_progress_revision INTEGER NOT NULL CHECK (base_progress_revision >= 0),
  course_revision       INTEGER NOT NULL,
  payload_json          TEXT    NOT NULL CHECK (json_valid(payload_json)),
  status                TEXT    NOT NULL
                        CHECK (status IN ('editing', 'ready', 'invalid', 'consumed', 'cancelled')),
  confirm_key           TEXT    UNIQUE,
  result_version_id     INTEGER,
  updated_at            TEXT    NOT NULL,
  UNIQUE (plan_id, revision),
  CHECK ((status = 'consumed' AND result_version_id IS NOT NULL AND confirm_key IS NOT NULL)
      OR (status <> 'consumed' AND result_version_id IS NULL)),
  FOREIGN KEY (plan_id, base_version)      REFERENCES plan_version(plan_id, version_no) ON DELETE RESTRICT,
  FOREIGN KEY (result_version_id, plan_id) REFERENCES plan_version(version_id, plan_id) ON DELETE RESTRICT
);

-- =====================================================================
-- 索引（14 个显式索引；PK/UQ 产生的自动索引另计）
-- =====================================================================
CREATE UNIQUE INDEX IF NOT EXISTS ux_single_course
  ON course ((1)) WHERE status = 'enabled';

CREATE UNIQUE INDEX IF NOT EXISTS ux_current_plan
  ON study_plan (student_id, course_id) WHERE status IN ('active', 'completed');

CREATE INDEX IF NOT EXISTS ix_concept_course ON concept (course_id, status, sort_order);
CREATE INDEX IF NOT EXISTS ix_prerequisite_to ON prerequisite (to_concept_id, course_id);
CREATE INDEX IF NOT EXISTS ix_resource_course ON resource (course_id, status);
CREATE INDEX IF NOT EXISTS ix_cr_resource ON concept_resource (resource_id, course_id);
CREATE INDEX IF NOT EXISTS ix_plan_owner ON study_plan (student_id, updated_at);
CREATE INDEX IF NOT EXISTS ix_task_concept ON plan_task (concept_id, course_id);
CREATE INDEX IF NOT EXISTS ix_vtask_task ON version_task (task_id, plan_id);
CREATE INDEX IF NOT EXISTS ix_slice_time ON task_slice (version_id, start_epoch);
CREATE INDEX IF NOT EXISTS ix_event_task ON learning_event (task_id, event_id);
CREATE INDEX IF NOT EXISTS ix_event_plan ON learning_event (plan_id, event_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_done_once
  ON learning_event (task_id) WHERE event_type = 'done';

CREATE INDEX IF NOT EXISTS ix_draft_plan ON plan_draft (plan_id, status);

-- =====================================================================
-- 触发器（13 个）：不可变 + sealed
-- =====================================================================
CREATE TRIGGER IF NOT EXISTS trg_pv_no_update BEFORE UPDATE ON plan_version
BEGIN SELECT RAISE(ABORT, '计划版本不可修改'); END;

CREATE TRIGGER IF NOT EXISTS trg_pv_no_delete BEFORE DELETE ON plan_version
BEGIN SELECT RAISE(ABORT, '计划版本不可删除'); END;

CREATE TRIGGER IF NOT EXISTS trg_vt_no_update BEFORE UPDATE ON version_task
BEGIN SELECT RAISE(ABORT, '版本任务不可修改'); END;

CREATE TRIGGER IF NOT EXISTS trg_vt_no_delete BEFORE DELETE ON version_task
BEGIN SELECT RAISE(ABORT, '版本任务不可删除'); END;

CREATE TRIGGER IF NOT EXISTS trg_ts_no_update BEFORE UPDATE ON task_slice
BEGIN SELECT RAISE(ABORT, '时间片不可修改'); END;

CREATE TRIGGER IF NOT EXISTS trg_ts_no_delete BEFORE DELETE ON task_slice
BEGIN SELECT RAISE(ABORT, '时间片不可删除'); END;

CREATE TRIGGER IF NOT EXISTS trg_val_no_update BEFORE UPDATE ON plan_validation
BEGIN SELECT RAISE(ABORT, '校验报告不可修改'); END;

CREATE TRIGGER IF NOT EXISTS trg_val_no_delete BEFORE DELETE ON plan_validation
BEGIN SELECT RAISE(ABORT, '校验报告不可删除'); END;

CREATE TRIGGER IF NOT EXISTS trg_ev_no_update BEFORE UPDATE ON learning_event
BEGIN SELECT RAISE(ABORT, '学习事件只追加，不可修改'); END;

CREATE TRIGGER IF NOT EXISTS trg_ev_no_delete BEFORE DELETE ON learning_event
BEGIN SELECT RAISE(ABORT, '学习事件只追加，不可删除'); END;

-- sealed：当前指针已到该版本后，禁止再补写历史子项
CREATE TRIGGER IF NOT EXISTS trg_vt_sealed BEFORE INSERT ON version_task
BEGIN
  SELECT RAISE(ABORT, '该版本已生效并冻结，不能补写版本任务')
  WHERE EXISTS (
    SELECT 1 FROM plan_version pv
    JOIN study_plan sp ON sp.plan_id = pv.plan_id
    WHERE pv.version_id = NEW.version_id
      AND sp.current_version IS NOT NULL
      AND sp.current_version >= pv.version_no
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_ts_sealed BEFORE INSERT ON task_slice
BEGIN
  SELECT RAISE(ABORT, '该版本已生效并冻结，不能补写时间片')
  WHERE EXISTS (
    SELECT 1 FROM version_task vt
    JOIN plan_version pv ON pv.version_id = vt.version_id
    JOIN study_plan sp ON sp.plan_id = pv.plan_id
    WHERE vt.version_id = NEW.version_id
      AND vt.task_id = NEW.task_id
      AND sp.current_version IS NOT NULL
      AND sp.current_version >= pv.version_no
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_val_sealed BEFORE INSERT ON plan_validation
BEGIN
  SELECT RAISE(ABORT, '该版本已生效并冻结，不能补写校验报告')
  WHERE EXISTS (
    SELECT 1 FROM plan_version pv
    JOIN study_plan sp ON sp.plan_id = pv.plan_id
    WHERE pv.version_id = NEW.version_id
      AND sp.current_version IS NOT NULL
      AND sp.current_version >= pv.version_no
  );
END;

-- ---------------------------------------------------------------- 模式版本
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1.0.0')
  ON CONFLICT(key) DO NOTHING;
INSERT INTO schema_meta (key, value) VALUES ('source_docs', 'D05 v1.0 / D02 v2.3')
  ON CONFLICT(key) DO NOTHING;
