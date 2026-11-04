from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import math,html
R=Path(__file__).resolve().parents[1]
class C:
 def __init__(self,w,h):
  self.w,self.h=w,h;self.im=Image.new('RGB',(w*2,h*2),'white');self.d=ImageDraw.Draw(self.im);self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">','<rect width="100%" height="100%" fill="white"/>']
 def line(self,p,dash=False,width=2):
  pp=[(x*2,y*2) for x,y in p]
  if dash:
   for (x,y),(xx,yy) in zip(p,p[1:]):
    n=max(1,int(math.hypot(xx-x,yy-y)/10))
    for i in range(0,n,2):self.d.line([(int(2*(x+(xx-x)*i/n)),int(2*(y+(yy-y)*i/n))),(int(2*(x+(xx-x)*min(i+1,n)/n)),int(2*(y+(yy-y)*min(i+1,n)/n)))],fill='#273444',width=width*2)
  else:self.d.line(pp,fill='#273444',width=width*2)
  self.svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in p)+f'" fill="none" stroke="#273444" stroke-width="{width}"'+(' stroke-dasharray="8 6"' if dash else '')+'/>')
 def text(self,x,y,s,size=28):
  f=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',size*2)
  for i,l in enumerate(s.split('\n')):
   yy=y+i*(size+9);self.d.text((x*2,yy*2),l,font=f,fill='black',anchor='mm');self.svg.append(f'<text x="{x}" y="{yy}" dominant-baseline="middle" text-anchor="middle" font-family="Microsoft YaHei,sans-serif" font-size="{size}">{html.escape(l)}</text>')
 def box(self,x,y,w,h,s,size=28,fill='#f3f6f9',kind='rect'):
  bb=(2*x,2*y,2*(x+w),2*(y+h))
  if kind=='diamond':
   pts=[(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)];self.d.polygon([(a*2,b*2) for a,b in pts],fill=fill,outline='#273444',width=4);self.svg.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in pts)+f'" fill="{fill}" stroke="#273444" stroke-width="2"/>')
  elif kind=='circle':
   self.d.ellipse(bb,fill=fill,outline='#273444',width=4);self.svg.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="#273444" stroke-width="2"/>')
  else:
   self.d.rounded_rectangle(bb,radius=(20 if kind=='round' else 0),fill=fill,outline='#273444',width=4);self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{10 if kind=="round" else 0}" fill="{fill}" stroke="#273444" stroke-width="2"/>')
  if s:self.text(x+w/2,y+h/2-(len(s.split('\n'))-1)*(size+9)/2,s,size)
 def arrow(self,p,label='',dash=False):
  self.line(p,dash);(x,y),(a,b)=p[-2:];ang=math.atan2(b-y,a-x);z=15
  self.line([(a-z*math.cos(ang-.45),b-z*math.sin(ang-.45)),(a,b),(a-z*math.cos(ang+.45),b-z*math.sin(ang+.45))])
  if label:self.text((p[0][0]+p[-1][0])/2,(p[0][1]+p[-1][1])/2-22,label,24)
 def save(self,n):
  self.im.save(R/(n+'.png'));(R/(n+'.svg')).write_text('\n'.join(self.svg+['</svg>']),encoding='utf-8')

