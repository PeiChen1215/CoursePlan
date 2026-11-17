import io

p = "D:/Gitproject/CoursePlan/backend/scripts/seed.py"
t = io.open(p, encoding="utf-8").read()

# 1) 要点字典（出题依据）
outlines = '''
# 知识点要点：测评出题的依据（管理员在「课程内容」里可改）
OUTLINES = {
    "软件过程与敏捷": "• 瀑布与迭代的区别：需求稳定性假设不同\\n• 敏捷的四个价值观：个体与交互、可用软件、客户合作、响应变化",
    "需求获取": "• 常见方法：访谈、问卷、观察、原型、文档分析\\n• 干系人识别决定需求是否完整",
    "用例建模": "• 参与者与用例：谁用系统做什么\\n• 包含/扩展关系：必须复用 vs 条件触发",
    "需求规格说明": "• 需求要可验证：避免“友好”“快速”这类不可测词\\n• 功能性需求 vs 非功能性需求",
    "结构化设计": "• 自顶向下、逐层分解；模块高内聚低耦合\\n• 数据流图到结构图的转换",
    "UML 类图": "• 关联、聚合（整体-部分，可独立存在）、组合（生命周期一致）\\n• 多重性：1、0..1、0..*、1..*",
    "设计模式入门": "• 创建型、结构型、行为型三类\\n• 单例与工厂的适用场景与代价",
    "程序流程图": "• 顺序、选择、循环三种基本结构\\n• 流程图与判定表的适用差异",
    "单元测试": "• 一个用例只验证一个行为；Arrange-Act-Assert\\n• 边界值、异常路径都要覆盖",
    "版本控制与分支": "• 分支模型：主干开发 vs 特性分支\\n• 提交粒度：一次提交只做一件事",
    "持续集成": "• 每次提交自动构建与测试\\n• 构建失败即停止合并",
    "代码评审": "• 关注正确性、可读性、可维护性，而非风格偏好\\n• 小批量评审更有效",
    "测试基础": "• 测试目的是发现缺陷，不是证明没有缺陷\\n• 测试级别：单元、集成、系统、验收",
    "等价类与边界值": "• 等价类划分：有效类与无效类\\n• 边界值：边界本身、边界±1",
    "判定表与场景法": "• 判定表用于多条件组合\\n• 场景法基于基本流与备选流",
    "白盒覆盖": "• 语句覆盖、判定覆盖、条件覆盖、路径覆盖\\n• 覆盖率不等于测试充分",
    "接口测试": "• 关注入参、出参、状态码与幂等\\n• 边界与异常入参优先",
    "自动化与持续测试": "• 稳定的用例才值得自动化\\n• 测试金字塔：多单元、少端到端",
}

'''
if "OUTLINES = {" not in t:
    anchor = "# (先修 → 后继)"
    assert anchor in t
    t = t.replace(anchor, outlines.lstrip("\n") + anchor, 1)
    print("seed: OUTLINES 已加入")

# 2) INSERT concept 带 outline
old_insert = '''            "INSERT INTO concept(course_id,name,chapter,difficulty,reference_minutes,"
            "sort_order,status) VALUES(1,?,?,?,?,?,'enabled')",
            (name, chapter, difficulty, minutes, order))'''
new_insert = '''            "INSERT INTO concept(course_id,name,chapter,difficulty,reference_minutes,"
            "outline,sort_order,status) VALUES(1,?,?,?,?,?,?,'enabled')",
            (name, chapter, difficulty, minutes, OUTLINES.get(name, ""), order))'''
assert old_insert in t, "第一门课的 INSERT 未匹配"
t = t.replace(old_insert, new_insert, 1)

old_insert2 = '''            "INSERT INTO concept(course_id,name,chapter,difficulty,reference_minutes,"
            "sort_order,status) VALUES(?,?,?,?,?,?,'enabled')",
            (second_id, name, chapter, difficulty, minutes, order))'''
new_insert2 = '''            "INSERT INTO concept(course_id,name,chapter,difficulty,reference_minutes,"
            "outline,sort_order,status) VALUES(?,?,?,?,?,?,?,'enabled')",
            (second_id, name, chapter, difficulty, minutes, OUTLINES.get(name, ""), order))'''
assert old_insert2 in t, "第二门课的 INSERT 未匹配"
t = t.replace(old_insert2, new_insert2, 1)

io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("seed: 概念已带要点")
