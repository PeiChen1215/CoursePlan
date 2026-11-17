import io

p = "D:/Gitproject/CoursePlan/backend/app/services/planner.py"
t = io.open(p, encoding="utf-8").read()

# generate：在 compute_capacity 之前剔除忙碌时段
old1 = '''        slots = expand_slots(availability, excluded, base_time, deadline)
        cap = compute_capacity(slots, self.config.BUFFER_RATIO)
        if cap.raw_minutes <= 0:
            raise StateError("E1003", "容量为零，无法排程")'''
new1 = '''        slots = expand_slots(availability, excluded, base_time, deadline)
        # 跨课程占位：其他计划已确认的时间片不能重复使用
        slots = subtract_busy(slots, busy)
        cap = compute_capacity(slots, self.config.BUFFER_RATIO)
        if cap.raw_minutes <= 0:
            raise StateError("E1003", "容量为零，无法排程")'''
assert old1 in t, "generate 段未匹配"
t = t.replace(old1, new1, 1)

# apply_overrides：同样支持 busy
old_sig = '''    def apply_overrides(self, plan_id: int, student_id: int, revision: int,'''
assert old_sig in t
seg_start = t.index(old_sig)
seg_end = t.index("slots = expand_slots", seg_start)
segment = t[seg_start:seg_end]
print("apply_overrides 签名片段：")
print(segment[:300])
