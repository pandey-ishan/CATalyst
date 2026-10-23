from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from rapidocr_onnxruntime import RapidOCR
from cat_analyst.parser import ocr_lines
from cat_analyst.math_ocr import restore_superscripts, raised_runs
out=Path('_test_artifacts');out.mkdir(exist_ok=True)
image=Image.new('RGB',(950,180),'white');draw=ImageDraw.Draw(image)
base=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
x=30
for text,raised in [('If 2',False),('(2+4+6+8+10+...+2x)',True),(' = (0.125)',False),('-80',True),(', the value of x will be _____.',False)]:
    font=small if raised else base
    draw.text((x,50 if raised else 58),text,font=font,fill='black')
    x+=draw.textlength(text,font=font)
image.save(out/'exponents-source.png')
frame=np.asarray(image)[:,:,::-1].copy()
engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
result,_=engine(frame)
lines=ocr_lines(result)
print('BEFORE',[(l.text,l.y,l.bottom) for l in lines])
repaired,notes,_=restore_superscripts(frame,lines,engine)
print('AFTER',[l.text for l in repaired],notes)

text=' '.join(l.text for l in repaired)
assert '^{(2+4+6+8+10+...+2x)}' in text, text
assert '^{-80}' in text, text
assert text.index('^{') < text.index('0.125') < text.index('^{-80}'), text
assert notes, 'Recovered math must remain visibly reviewable'
print('SUPERSCRIPT OCR SMOKE PASSED')
