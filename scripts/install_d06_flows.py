"""把用户重画的 12 张程序流程图转成真 PNG 并按 D06 图号就位。"""
from pathlib import Path

from PIL import Image

ROOT = Path(r"D:\Gitproject\CoursePlan")
SRC = ROOT / "docs" / "04_实现" / "程序流程图"
DST = ROOT / "docs" / "04_实现" / "figures"

# 用户文件 → D06 图号
MAP = [
    ("02_用户登录流程图.png", "fig-3-2-flow-m01.png", "第 3 章 M-01 登录判定"),
    ("03_批量导入先修关系流程图.png", "fig-4-2-flow-m02.png", "第 4 章 M-02 先修批量提交"),
    ("04_手动填写约束与容量估算流程图.png", "fig-5-2-flow-m03.png", "第 5 章 M-03 约束提交"),
    ("05_自然语言填写约束流程图.png", "fig-6-2-flow-m04.png", "第 6 章 M-04 抽取与追问"),
    ("06_学习计划草案生成流程图.png", "fig-7-2-flow-m05.png", "第 7 章 M-05 草案生成"),
    ("07_学习计划草案校验流程图.png", "fig-8-2-flow-m06.png", "第 8 章 M-06 计划校验"),
    ("08_草案确认与版本提交流程图.png", "fig-9-2-flow-m09.png", "第 9 章 M-07 确认与版本"),
    ("09_学习任务完成事件提交流程图.png", "fig-10-2-flow-m08.png", "第 10 章 M-08 进度与事件"),
    ("11_HTTP 请求处理与异常映射流程图.png", "fig-12-2-flow-m10.png", "第 12 章 M-10 请求管道"),
    ("12_工作单元事务与写入控制流程图.png", "fig-13-2-flow-m11.png", "第 13 章 M-11 事务"),
    ("01_系统启动与配置加载流程图.png", "fig-14-2-flow-m12.png", "第 14 章 M-12 配置装配"),
]


def main():
    for src_name, dst_name, desc in MAP:
        src = SRC / src_name
        img = Image.open(src)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = DST / dst_name
        img.save(out, "PNG", optimize=True)
        print("%-34s → %-26s %s  %dx%d" % (src_name, dst_name, desc, img.width, img.height))


if __name__ == "__main__":
    main()
