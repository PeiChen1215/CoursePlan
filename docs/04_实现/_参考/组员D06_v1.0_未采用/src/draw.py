from pathlib import Path
import canvas
from canvas import C
R=Path(__file__).resolve().parents[1];canvas.R=R/'figures'

def title(c,s):c.text(c.w/2,35,s,30)
def flow():
 c=C(1300,1420);title(c,'图2  确定性排程程序流程图')
 nodes=[(420,80,440,65,'开始', 'round'),(330,180,620,90,'读取快照、基准时间及固定配置','rect'),(330,310,620,100,'补齐目标先修闭包；稳定拓扑排序\n拆成学习 / 练习逻辑任务','rect'),(330,450,620,95,'展开有效时段；扣除各段尾部缓冲\n保留已完成任务，装入待排任务','rect'),(440,590,400,140,'还有待排任务？','diamond'),(330,780,620,85,'求满足先修的最早可用分钟\n按 ≤120 分钟切片','rect'),(330,920,620,140,'记录已排切片及剩余分钟\n取下一任务；先修不满足则全部未排','rect'),(330,1120,620,90,'合并已排 / 未排任务；执行完整校验\n生成草案、错误列表及输入摘要','rect'),(420,1280,440,65,'返回草案（不直接生效）','round')]
 for x,y,w,h,s,k in nodes:c.box(x,y,w,h,s,26,kind=k)
 for a,b in [(145,180),(270,310),(410,450),(545,590),(730,780),(865,920),(1210,1280)]:c.arrow([(640,a),(640,b)])
 c.text(680,752,'是',22);c.arrow([(440,660),(120,660),(120,1165),(330,1165)]);c.text(150,695,'否',22)
 c.arrow([(950,990),(1110,990),(1110,710),(950,710),(950,660),(840,660)]);c.text(1150,850,'继续遍历',22)
 c.text(640,1085,'所有任务遍历完毕后统一校验',22)
 c.save('02_排程程序流程图')

def ns():
 c=C(1200,1070);title(c,'图3  计划校验 N-S 图（结构化盒图）')
 c.box(80,85,1040,75,'检查输入结构、时间格式与引用完整性',26)
 c.box(80,160,1040,250,'',fill='white');c.line([(80,160),(600,240),(1120,160)]);c.text(600,188,'输入结构有效？',25);c.text(160,220,'否',23);c.text(1040,220,'是',23);c.line([(600,240),(600,410)])
 c.text(340,305,'记录结构错误\n不执行依赖该结构的检查',25);c.text(850,285,'依次检查：容量、重叠、先修、截止\n收集全部业务错误，不短路',24)
 c.box(80,410,1040,90,'遍历所有可解析任务 / 切片 / 先修边',26);c.box(80,500,75,280,'',fill='#e8edf3');c.box(155,500,965,75,'执行当前条目检查；追加错误及定位信息',25);c.box(155,575,965,205,'',fill='white');c.line([(155,575),(640,650),(1120,575)]);c.text(640,602,'发现异常？',25);c.text(230,635,'是',22);c.text(1040,635,'否',22);c.line([(640,650),(640,780)]);c.text(395,710,'记录错误码、任务及切片位置',23);c.text(880,710,'继续下一条目',24)
 c.box(80,780,1040,85,'去重并稳定排序 issues；计算容量、负载和未排分钟',25);c.box(80,865,1040,100,'输出 ValidationReport：passed = 不含 ERROR\nWARN 可确认，ERROR 不可确认',25);c.text(600,1010,'说明：外框为顺序结构；窄侧栏与条件行构成遍历结构。',22);c.save('03_校验算法_NS图')

def pad():
 c=C(1420,860);title(c,'图4  登录处理 PAD 图')
 c.line([(80,100),(80,740)]);c.box(80,110,480,75,'校验用户名 / 密码输入格式',25)
 c.box(80,225,480,75,'读取账户；未知账户做等价哈希校验',24)
 # PAD choice: left spine -> condition with inward right notch, branches rightward.
 c.line([(80,360),(480,360),(445,405),(480,450),(80,450)]);c.text(275,400,'账户可登录且密码匹配？',24)
 c.line([(480,360),(650,360)]);c.text(590,335,'是',22);c.box(650,325,680,75,'清零失败次数；签发 24 小时会话',25)
 c.line([(480,450),(650,450)]);c.text(590,430,'否',22);c.box(650,415,680,75,'认证失败；仅可计数账户累计失败次数',23)
 c.line([(650,490),(650,670)]);c.line([(650,550),(980,550),(950,590),(980,630),(650,630)]);c.text(805,586,'本次达到第 5 次失败？',22)
 c.line([(980,550),(1050,550)]);c.text(1015,528,'是',20);c.box(1050,520,310,65,'锁定至基准时间 +5 分钟',20)
 c.line([(980,630),(1050,630)]);c.text(1015,608,'否',20);c.box(1050,600,310,65,'保留失败计数',22)
 c.box(80,700,480,65,'提交认证状态；返回结果',24);c.text(720,815,'顺序沿左侧竖线自上而下；选择分支向右展开，无流程箭头。',23);c.save('04_登录处理_PAD图')

def decision():
 c=C(1400,720);title(c,'图5  计划确认判定表')
 rows=[['条件 / 动作','R1','R2','R3','R4','R5','R6'],['A 当前用户有权确认？','N','Y','Y','Y','Y','Y'],['B 确认键已有同请求结果？','—','Y','N','N','N','N'],['C 版本 / 进度 / 课程基线一致？','—','—','N','Y','Y','Y'],['D 草案状态允许确认？','—','—','—','N','Y','Y'],['E 重校验无 ERROR 且时段仍有效？','—','—','—','—','N','Y'],['拒绝访问（不泄露他人记录）','×','','','','',''],['返回原确认结果','','×','','','',''],['返回 E2004，要求刷新预览','','','×','','',''],['返回 E1003 状态冲突','','','','×','',''],['返回 E2003，保留草案错误','','','','','×',''],['原子保存新版本并移动当前指针','','','','','','×']]
 for i,row in enumerate(rows):
  for j,t in enumerate(row):c.box(40+(590 if j else 0)+(j-1)*120 if j else 40,85+i*47,590 if j==0 else 120,47,t,21,fill='#e8edf3' if i in [0,6] else 'white')
 c.text(700,690,'Y=是；N=否；—=与该规则无关；×=执行。各列按首个失败条件划分，互斥且完备。',22);c.save('05_计划确认_判定表')
 c=C(1550,820);title(c,'图6  计划确认判定树（与图5规则一致）')
 ys=[115,245,375,505,635];labels=['A 有确认权限','B 确认键已成功','C 基线一致','D 草案可确认','E 重校验通过'];actions=['拒绝访问 R1','返回原结果 R2','刷新预览 R3','状态冲突 R4','返回校验错误 R5']
 for i,(y,s,a) in enumerate(zip(ys,labels,actions)):
  x=40+i*180;c.box(x,y,310,65,s,23);right='否' if i!=1 else '是';down='是' if i!=1 else '否';c.arrow([(x+310,y+32),(1270,y+32)]);c.box(1270,y,245,65,a,22);c.text(1120,y+10,right,21)
  if i<4:c.arrow([(x+155,y+65),(x+155,y+100),(x+335,y+100),(x+335,ys[i+1])]);c.text(x+100,y+93,down,20)
  else:c.arrow([(x+155,y+65),(x+155,760),(1270,760)]);c.text(x+190,725,'是',21);c.box(1270,727,245,65,'保存新版本 R6',22)
 c.save('06_计划确认_判定树')

def jackson():
 c=C(1440,900);title(c,'图7  草案结果数据结构 Jackson 图')
 def b(x,y,w,s,mark=''):
  c.box(x,y,w,75,s,24,fill='white')
  if mark:c.text(x+w-15,y+14,mark,25)
 b(500,90,440,'DraftResult');xs=[30,380,730,1080];names=['草案及基线标识','约束 / 课程快照','任务项','校验报告']
 c.line([(720,165),(720,210),(205,210),(1255,210)])
 for x,s in zip(xs,names):c.line([(x+175,210),(x+175,245)]);b(x,245,350,s,'*' if s=='任务项' else '')
 c.line([(905,320),(905,380),(200,380),(1200,380)]);c.line([(200,380),(200,420)]);b(30,420,340,'切片（开始 / 结束）','*')
 for x,s in [(390,'任务标识 / 类型 / 时长'),(1030,'排程结果')]:c.line([(x+170,380),(x+170,420)]);b(x,420,340,s)
 c.line([(1200,495),(1200,550),(895,550),(1265,550)])
 b(730,590,330,'全部排定','○');b(1100,590,310,'尚有未排','○');c.line([(895,550),(895,590)]);c.line([(1265,550),(1255,590)])
 c.line([(895,665),(895,710)]);b(730,710,330,'剩余分钟 = 0');c.line([(1255,665),(1255,710)]);b(1100,710,310,'未排分钟 / 原因')
 c.text(720,850,'无标记：顺序组成；○：互斥选择；*：重复。切片可为空；部分排定保留已有切片及剩余分钟。',23);c.save('07_草案数据结构_Jackson图')

def structure():
 c=C(1500,780);title(c,'图1  程序模块结构与主要调用关系')
 c.box(460,85,580,75,'M09 学生 / 管理员界面',28);c.box(460,220,580,75,'M10 API 路由与 DTO 校验',28);c.arrow([(750,160),(750,220)])
 cols=[(25,'M01 认证权限\nM02 课程内容\nM03 学习约束'),(515,'M04 追问抽取\nM05 分解排程\nM06 计划校验'),(1005,'M07 确认版本\nM08 进度事件')]
 c.line([(750,295),(750,330),(260,330),(1240,330)])
 for x,s in cols:c.arrow([(x+235,330),(x+235,380)]);c.box(x,380,470,155,s,26)
 c.box(60,630,650,80,'M11 仓储 / 事务 → SQLite',27);c.box(790,630,650,80,'M12 时钟 / 配置 / 日志 / LLM适配',25)
 for x in [260,750,1240]:c.line([(x,535),(x,580)])
 c.line([(260,580),(1240,580)]);c.arrow([(385,580),(385,630)]);c.arrow([(1115,580),(1115,630)]);c.text(750,750,'连线表示接口调用 / 依赖；领域算法通过端口访问外部能力。',23);c.save('01_程序模块结构图')

def pdl():
 c=C(1500,1000);title(c,'图8  排程核心 PDL（伪代码）')
 lines=['PROCEDURE BuildDraft(snapshot, base_time, config)', '  REQUIRE valid snapshot AND acyclic prerequisites', '  concepts := Closure(targets) - explicitly_mastered', '  tasks := SplitStudyPractice(StableTopological(concepts))', '  slots := ExpandAndClip(availability, base_time, deadline)', '  usable := ReserveTail(slots, CEIL(slot_minutes * 0.10))', '  result := KeepCompletedTasksUnchanged(snapshot)', '  FOR EACH task IN dependency_order', '    ready := LatestFinishOfAllRequiredPredecessors(task)', '    slices, remaining := FillEarliest(usable, ready, max_slice=120)', '    ADD task WITH slices AND remaining TO result', '    IF remaining > 0 THEN mark task UNSCHEDULED', '  END FOR', '  report := ValidateAll(result, snapshot, config)', '  RETURN Draft(result, report, hash(snapshot, base_time, config))', 'END PROCEDURE']
 for i,s in enumerate(lines):
  # use left aligned text via fixed column positioning
  c.d.text((80*2,(100+i*50)*2),s,font=__import__('PIL').ImageFont.truetype('C:/Windows/Fonts/consola.ttf',40),fill='black')
  import html;c.svg.append(f'<text x="80" y="{100+i*50+20}" font-family="Consolas,monospace" font-size="20">{html.escape(s)}</text>')
 c.text(750,950,'说明：先修未完成时不安排后继任务；剩余分钟作为未排任务保留，供校验报告定位。',23);c.save('08_排程核心_PDL')

if __name__=='__main__':
 structure();flow();ns();pad();decision();jackson();pdl()
