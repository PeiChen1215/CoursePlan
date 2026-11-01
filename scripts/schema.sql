-- =====================================================================
-- 学径 StudyPath —— 课程学习规划辅助系统
-- 数据库：studyplan.db（SQLite 3.35+）
-- 对应文档：D05 数据库设计说明书 v0.1（§3.2 表清单、§3.3 索引与约束、§4.1 数据字典）
-- 说明：全部语句幂等，可重复执行；先建 schema_meta 与主表，再建带外键的子表。
-- =====================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 3000;

-- ---------------------------------------------------------------- 元数据
CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- ---------------------------------------------------------------- 账号与课程
CREATE TABLE IF NOT EXISTS app_user (
  user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL,
  password_hash TEXT    NOT NULL,
  role          TEXT    NOT NULL CHECK (role IN ('student', 'admin')),
  status        TEXT    NOT NULL DEFAULT 'enabled' CHECK (status IN ('enabled', 'locked')),
  created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS course (
  course_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT    NOT NULL,
  description TEXT,
  semester    TEXT    NOT NULL,
  total_hours INTEGER NOT NULL CHECK (total_hours > 0),
  status      TEXT    NOT NULL DEFAULT 'enabled' CHECK (status IN ('enabled', 'disabled'))
);

CREATE TABLE IF NOT EXISTS concept (
  concept_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id         INTEGER NOT NULL REFERENCES course(course_id) ON DELETE RESTRICT,
  name              TEXT    NOT NULL,
  chapter           TEXT    NOT NULL,
  difficulty        INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
  reference_minutes INTEGER NOT NULL CHECK (reference_minutes BETWEEN 5 AND 600),
  objectives        TEXT,
  pitfalls          TEXT,
  sort_order        INTEGER NOT NULL DEFAULT 1 CHECK (sort_order >= 1),
  status            TEXT    NOT NULL DEFAULT 'enabled' CHECK (status IN ('enabled', 'disabled'))
);

CREATE TABLE IF NOT EXISTS prerequisite (
  prereq_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id       INTEGER NOT NULL REFERENCES course(course_id) ON DELETE RESTRICT,
  from_concept_id INTEGER NOT NULL REFERENCES concept(concept_id) ON DELETE RESTRICT,
  to_concept_id   INTEGER NOT NULL REFERENCES concept(concept_id) ON DELETE RESTRICT,
  CHECK (from_concept_id <> to_concept_id)
);

CREATE TABLE IF NOT EXISTS resource (
  resource_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id    INTEGER NOT NULL REFERENCES course(course_id) ON DELETE RESTRICT,
  title        TEXT    NOT NULL,
  type         TEXT    NOT NULL CHECK (type IN ('document', 'video', 'exercise', 'link')),
  url          TEXT    CHECK (url IS NULL OR url LIKE 'http://%' OR url LIKE 'https://%'),
  summary      TEXT,
  read_minutes INTEGER CHECK (read_minutes IS NULL OR read_minutes BETWEEN 0 AND 240),
  status       TEXT    NOT NULL DEFAULT 'enabled' CHECK (status IN ('enabled', 'disabled')),
  CHECK (url IS NOT NULL OR summary IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS concept_resource (
  concept_id  INTEGER NOT NULL REFERENCES concept(concept_id) ON DELETE RESTRICT,
  resource_id INTEGER NOT NULL REFERENCES resource(resource_id) ON DELETE RESTRICT,
  PRIMARY KEY (concept_id, resource_id)
);

-- ---------------------------------------------------------------- 计划与约束
CREATE TABLE IF NOT EXISTS study_plan (
  plan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id      INTEGER NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
  course_id       INTEGER NOT NULL REFERENCES course(course_id) ON DELETE RESTRICT,
  status          TEXT    NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'pending', 'active', 'done', 'archived')),
  current_version INTEGER NOT NULL DEFAULT 0 CHECK (current_version >= 0),
  created_at      TEXT    NOT NULL,
  updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_constraint (
  constraint_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id             INTEGER NOT NULL UNIQUE REFERENCES study_plan(plan_id) ON DELETE RESTRICT,
  target_concept_id   INTEGER NOT NULL REFERENCES concept(concept_id) ON DELETE RESTRICT,
  extra_concept_ids   TEXT,
  deadline            TEXT    NOT NULL,
  availability        TEXT    NOT NULL,
  excluded_dates      TEXT,
  mastered_concept_ids TEXT,
  base_time           TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_task (
  task_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id           INTEGER NOT NULL REFERENCES study_plan(plan_id) ON DELETE RESTRICT,
  concept_id        INTEGER NOT NULL REFERENCES concept(concept_id) ON DELETE RESTRICT,
  type              TEXT    NOT NULL CHECK (type IN ('study', 'practice')),
  estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes BETWEEN 1 AND 1440),
  scheduled_date    TEXT,
  start_time        TEXT,
  end_time          TEXT,
  status            TEXT    NOT NULL DEFAULT 'undone' CHECK (status IN ('undone', 'done'))
);

CREATE TABLE IF NOT EXISTS plan_version (
  version_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id       INTEGER NOT NULL REFERENCES study_plan(plan_id) ON DELETE RESTRICT,
  version       INTEGER NOT NULL CHECK (version >= 1),
  change_reason TEXT    NOT NULL
                CHECK (change_reason IN ('initial', 'delay', 'goal_change',
                                         'availability_change', 'duration_change', 'manual')),
  change_note   TEXT    NOT NULL,
  snapshot      TEXT    NOT NULL,
  operator_id   INTEGER NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
  created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_validation (
  validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  version_id    INTEGER NOT NULL REFERENCES plan_version(version_id) ON DELETE RESTRICT,
  passed        INTEGER NOT NULL CHECK (passed IN (0, 1)),
  issues        TEXT    NOT NULL,
  metrics       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_event (
  event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id        INTEGER NOT NULL REFERENCES study_plan(plan_id) ON DELETE RESTRICT,
  task_id        INTEGER NOT NULL REFERENCES plan_task(task_id) ON DELETE RESTRICT,
  event_type     TEXT    NOT NULL CHECK (event_type IN ('done', 'correction', 'note')),
  actual_minutes INTEGER CHECK (actual_minutes IS NULL OR actual_minutes >= 0),
  note           TEXT,
  occurred_at    TEXT    NOT NULL,
  operator_id    INTEGER NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT
);

-- ---------------------------------------------------------------- 索引（13 个）
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_username ON app_user (username);

CREATE UNIQUE INDEX IF NOT EXISTS ux_concept_course_name ON concept (course_id, name);
CREATE INDEX IF NOT EXISTS ix_concept_course ON concept (course_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_prereq_pair ON prerequisite (from_concept_id, to_concept_id);
CREATE INDEX IF NOT EXISTS ix_prereq_to ON prerequisite (to_concept_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_plan_active
  ON study_plan (student_id, course_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS ix_plan_student ON study_plan (student_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_concept_type
  ON plan_task (plan_id, concept_id, type);
CREATE INDEX IF NOT EXISTS ix_task_plan_date ON plan_task (plan_id, scheduled_date);

CREATE UNIQUE INDEX IF NOT EXISTS ux_version_plan_no ON plan_version (plan_id, version);
CREATE UNIQUE INDEX IF NOT EXISTS ux_validation_version ON plan_validation (version_id);

CREATE INDEX IF NOT EXISTS ix_event_task_time ON learning_event (task_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_event_plan_time ON learning_event (plan_id, occurred_at);

-- ---------------------------------------------------------------- 数据版本
INSERT INTO schema_meta (key, value) VALUES ('data_version', '1')
  ON CONFLICT(key) DO NOTHING;
INSERT INTO schema_meta (key, value) VALUES ('schema_of', 'D05 v0.1 / D02 v2.3')
  ON CONFLICT(key) DO NOTHING;
