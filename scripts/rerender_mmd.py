"""重新渲染指定的 .mmd 源文件为 PNG（就地覆盖）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "02_需求" / "figures"
TMP = ROOT / ".tmp_work"

JOBS = [
    ("fig-3-4-sequence", (2400, 2600)),
    ("fig-3-8-er", (2800, 2400)),
]


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    for name, win in JOBS:
        src = (FIG / "src" / (name + ".mmd")).read_text(encoding="utf-8")
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_mermaid(src, win), str(raw), win)
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-22s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()
