import io
p = "docs/04_实现/D06_详细设计说明书_v0.1_20261103.md"
t = io.open(p, encoding="utf-8").read()
t = t.replace("图 2-1 按**调用层次**组织：M-10", "本图按**调用层次**组织：M-10")
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("ok")
