"""直接跑出题服务，定位 500 的真实原因（真实模型）。"""
import sys
import traceback

sys.path.insert(0, ".")

from app.core import config as C
from app.db.uow import Database
from app.services import assessment as svc
from app.services.provider import build_provider

cfg = C.load({"DB_PATH": r"D:\Gitproject\CoursePlan\data\dev_ui.db"})
print("provider mode:", cfg.PROVIDER_MODE, "| key 长度:", len(cfg.PROVIDER_KEY or ""))
provider = build_provider(cfg.PROVIDER_MODE, cfg.PROVIDER_KEY,
                          cfg.MODEL_TIMEOUT_SECONDS, None, cfg.PROVIDER_BASE,
                          cfg.PROVIDER_MODEL, cfg.PROVIDER_THINKING)
print("provider name:", provider.name)

db = Database(cfg.db_file)
db.init_schema(open("../scripts/schema.sql", encoding="utf-8").read())
rows = db.query("SELECT * FROM concept WHERE concept_id = 6")
concept = rows[0]
print("concept keys:", list(concept.keys())[:6], "| outline:", (concept["outline"] or "")[:30])
resources = db.query(
    "SELECT r.summary FROM resource r JOIN concept_resource cr ON cr.resource_id = r.resource_id"
    " WHERE cr.concept_id = 6 AND r.status = 'enabled'")
try:
    title, items, mode, reason = svc.generate_items(provider, concept, resources)
    print("title:", title, "| items:", len(items), "| mode:", mode, "| reason:", reason)
    for item in items:
        print("  ", item["no"], item["type"], item["stem"][:40])
except Exception:
    traceback.print_exc()
