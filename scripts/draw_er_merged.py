"""合并版全库概念 ER 图（v3）：矩形实体 + 菱形联系 + 基数，不画属性椭圆。"""
from PIL import Image, ImageDraw, ImageFont

W, H = 2400, 1990
INK = (26, 26, 28)
GRAY = (104, 106, 112)
LINE = (50, 52, 56)
FONT = "C:/Windows/Fonts/msyh.ttc"
BOLD = "C:/Windows/Fonts/msyhbd.ttc"

EW, EH = 224, 88
DW, DH = 128, 76
GAP = 46

img = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(img)


def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def text(xy, s, size=26, bold=False, fill=INK, anchor="mm"):
    d.text(xy, s, font=f(size, bold), fill=fill, anchor=anchor)


def entity(cx, cy, cn, en):
    d.rectangle([cx - EW // 2, cy - EH // 2, cx + EW // 2, cy + EH // 2],
                outline=INK, width=3, fill=(250, 250, 252))
    text((cx, cy - 15), cn, 34, True)
    text((cx, cy + 19), en, 18, False, GRAY)


def diamond(cx, cy, label):
    d.polygon([(cx, cy - DH // 2), (cx + DW // 2, cy), (cx, cy + DH // 2), (cx - DW // 2, cy)],
              outline=INK, fill=(255, 255, 255), width=3)
    text((cx, cy), label, 26, True)


def seg(p1, p2, label=None, at=0.2, dx=0, dy=-15, dash=False):
    (x1, y1), (x2, y2) = p1, p2
    if dash:
        import math
        total = math.hypot(x2 - x1, y2 - y1) or 1
        cur = 0.0
        while cur < total:
            t0, t1 = cur / total, min((cur + 10) / total, 1.0)
            d.line([(x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0),
                    (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1)], fill=LINE, width=2)
            cur += 18
    else:
        d.line([p1, p2], fill=LINE, width=2)
    if label:
        text((x1 + (x2 - x1) * at + dx, y1 + (y2 - y1) * at + dy), label, 21, True)


def panel(x1, y1, x2, y2, title):
    d.rounded_rectangle([x1, y1, x2, y2], radius=12, outline=(176, 178, 184), width=2)
    text((x1 + 18, y1 + 24), title, 27, True, (64, 66, 72), "lm")


def hrow(y, items, start_x=96):
    pos, pending = {}, {}
    cursor = start_x
    sequence = []
    for item in items:
        if item[0] == "e":
            cx = cursor + EW // 2
            entity(cx, y, item[2], item[3])
            pos[item[1]] = (cx, y)
            sequence.append(("e", item[1], cx))
            cursor += EW + GAP
        else:
            cx = cursor + DW // 2
            diamond(cx, y, item[1])
            sequence.append(("r", item[1], cx, item[2], item[3]))
            cursor += DW + GAP
    for index, node in enumerate(sequence):
        if node[0] != "r":
            continue
        _, label, cx, left_card, right_card = node
        left = pos[sequence[index - 1][1]]
        right = pos[sequence[index + 1][1]]
        seg((left[0] + EW // 2, y), (cx - DW // 2, y), left_card)
        seg((cx + DW // 2, y), (right[0] - EW // 2, y), right_card)
    return pos


# ================= ① 课程内容 =================
panel(52, 60, 2348, 680, "① 课程内容域")
A1 = [("e", "user", "用户", "app_user"), ("r", "维护", "1", "N"),
      ("e", "course", "课程", "course"), ("r", "拥有", "1", "N"),
      ("e", "concept", "知识点", "concept"), ("r", "关联", "M", "N"),
      ("e", "resource", "资源", "resource")]
pA = hrow(270, A1)

# 课程—资源：属于（顶部走线，不穿过知识点）
seg((pA["course"][0], 270 - EH // 2), (pA["course"][0], 170))
seg((pA["course"][0], 170), (1300, 170), "1")
diamond(1300, 170, "属于")
seg((1300 + DW // 2, 170), (pA["resource"][0], 170), "N")
seg((pA["resource"][0], 170), (pA["resource"][0], 270 - EH // 2))

# 知识点—先修关系（自反联系落表）
seg((pA["concept"][0], 270 + EH // 2), (pA["concept"][0], 400), "1", at=0.35, dx=22, dy=-2)
diamond(pA["concept"][0], 436, "先修")
seg((pA["concept"][0], 472), (pA["concept"][0], 560 - EH // 2), "N", at=0.55, dx=22, dy=-2)
entity(pA["concept"][0], 560, "先修关系", "prerequisite")
text((pA["concept"][0] + 145, 512), "自反联系：前置知识点是知识点的角色视图", 19, False, GRAY, "lm")

# 知识点—资源（多对多，落表 concept_resource）
entity(pA["resource"][0], 560, "知识点资源", "concept_resource")
seg((1300 + DW // 2 - 6, 202), (pA["resource"][0], 560 - EH // 2), None, dash=True)
text((pA["resource"][0] - 10, 380), "多对多落表", 19, False, GRAY, "lm")

# ================= ② 计划、版本与任务 =================
panel(52, 700, 2348, 1560, "② 计划、版本与任务域")
B1 = [("e", "plan", "学习计划", "study_plan"), ("r", "受约束", "1", "1"),
      ("e", "cons", "当前约束", "plan_constraint"), ("r", "暂存", "1", "N"),
      ("e", "draft", "持久化草案", "plan_draft"), ("r", "分解", "1", "N"),
      ("e", "task", "稳定逻辑任务", "plan_task")]
pB1 = hrow(880, B1)

B2 = [("e", "version", "计划版本", "plan_version"), ("r", "安排", "1", "N"),
      ("e", "vtask", "版本任务", "version_task"), ("r", "记录", "1", "N"),
      ("e", "event", "学习事件", "learning_event")]
pB2 = hrow(1230, B2)
pB3 = hrow(1480, [("e", "valid", "校验报告", "plan_validation")], start_x=96)
pB3b = hrow(1480, [("e", "slice", "时间片", "task_slice")], start_x=96 + 210 + 52 + 124 + 52)

# 学习计划 → 计划版本（生成）
seg((pB1["plan"][0], 880 + EH // 2), (pB1["plan"][0], 1022), "1", at=0.45, dx=22, dy=-2)
diamond(pB1["plan"][0], 1058, "生成")
seg((pB1["plan"][0], 1094), (pB1["plan"][0], 1230 - EH // 2), "N", at=0.5, dx=22, dy=14)

# 计划版本 → 校验报告（1:1）
seg((pB2["version"][0], 1230 + EH // 2), (pB2["version"][0], 1330), "1", at=0.45, dx=22, dy=-2)
diamond(pB2["version"][0], 1366, "校验")
seg((pB2["version"][0], 1402), (pB2["version"][0], 1480 - EH // 2), "1", at=0.5, dx=22, dy=12)
text((pB2["version"][0] + 160, 1368), "1:1，仅保留生效版本", 19, False, GRAY, "lm")

# 版本任务 → 时间片（切片）
seg((pB3b["slice"][0], 1230 + EH // 2), (pB3b["slice"][0], 1330), "1", at=0.45, dx=22, dy=-2)
diamond(pB3b["slice"][0], 1366, "切片")
seg((pB3b["slice"][0], 1402), (pB3b["slice"][0], 1480 - EH // 2), "N", at=0.5, dx=22, dy=12)

# 稳定任务 ↔ 版本任务（对应）
seg((pB1["task"][0], 880 + EH // 2), (pB1["task"][0], 1104))
seg((pB1["task"][0], 1104), (pB2["vtask"][0], 1104), "N", at=0.5, dy=-16)
diamond(pB2["vtask"][0], 1140, "对应")
seg((pB2["vtask"][0], 1176), (pB2["vtask"][0], 1230 - EH // 2), "1", at=0.6, dx=22, dy=10)

# ================= ③ 课程测评 =================
panel(52, 1580, 2348, 1900, "③ 课程测评与元数据")
C1 = [("e", "paper", "测评试卷", "assessment_paper"), ("r", "作答", "1", "N"),
      ("e", "attempt", "测评作答", "assessment_attempt"), ("r", "明细", "1", "N"),
      ("e", "item", "逐题明细", "assessment_item")]
pC = hrow(1740, C1)

entity(2010, 1740, "模式元数据", "schema_meta")
text((2010, 1812), "单行元数据表，无外键", 19, False, GRAY)

# ================= 图注 =================
text((76, 1940),
     "跨域联系：计划任务—引用(N:1)—知识点；测评试卷—依据(1:N)—知识点、—归属(N:1)—课程；"
     "测评作答—属于(N:1)—学生、—含卷(N:1)—试卷；逐题明细—属于(N:1)—作答。",
     20, False, GRAY, "lm")
text((76, 1968),
     "记法：矩形=实体（中文名 / 物理表名），菱形=联系，连线旁 1 / N / M 为最大基数；"
     "按教师意见不画属性椭圆，属性与主键见 §4.1 数据字典。",
     20, False, GRAY, "lm")

img.save("D:/Gitproject/CoursePlan/docs/03_设计/figures/d05-er-merged.png")
print("saved", img.size)
