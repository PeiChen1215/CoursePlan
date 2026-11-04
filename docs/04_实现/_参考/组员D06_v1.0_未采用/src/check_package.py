from pathlib import Path
from itertools import product
import json,zipfile,math
from docx import Document
R=Path(__file__).resolve().parents[1]
patterns=[(0,None,None,None,None),(1,1,None,None,None),(1,0,0,None,None),(1,0,1,0,None),(1,0,1,1,0),(1,0,1,1,1)]
for values in product((0,1),repeat=5):
 matches=[p for p in patterns if all(a is None or a==v for a,v in zip(p,values))]
 assert len(matches)==1,(values,matches)
assert math.ceil(30*.7)==21 and 30-math.ceil(30*.7)==9
assert 61-math.ceil(61*.1)==54
doc=next(R.glob('D06*.docx'));d=Document(doc)
assert len(d.inline_shapes)==8
assert len(list((R/'figures').glob('*.png')))==8
assert len(list((R/'figures').glob('*.svg')))==8
report=json.loads((R/'结构核对.json').read_text(encoding='utf-8'));report['decision_table_boolean_combinations']=32;report['decision_table_mutually_exclusive_and_exhaustive']=True;report['numeric_examples_checked']=True
(R/'结构核对.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
out=R.parent/'课程学习规划辅助系统_D06详细设计及图示_v1.0.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for p in R.rglob('*'):
  if p.is_file() and '.work' not in p.parts and '__pycache__' not in p.parts and p.name!='finalize.py':z.write(p,p.relative_to(R))
with zipfile.ZipFile(out) as z:assert z.testzip() is None
print(str(doc));print(str(out));print('包文件数',len(z.namelist()))
