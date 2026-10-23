"""Safe rich-text rendering of plain stored questions and explicit exponents."""
import html
import re


def math_html(text: str) -> str:
    output=[]
    i=0
    while i<len(text):
        if text[i]=='^' and i+1<len(text):
            start=i+1
            if text[start] in '{(':
                opening=text[start];closing='}' if opening=='{' else ')'
                depth=1;j=start+1
                while j<len(text) and depth:
                    if text[j]==opening:depth+=1
                    elif text[j]==closing:depth-=1
                    j+=1
                if depth==0:
                    output.append('<sup>'+math_html(text[start+1:j-1])+'</sup>')
                    i=j
                    continue
            else:
                match=re.match(r'-?(?:\d+(?:\.\d+)?|[a-zA-Z])',text[start:])
                if match:
                    output.append('<sup>'+html.escape(match[0])+'</sup>')
                    i=start+len(match[0]);continue
        output.append('<br>' if text[i]=='\n' else html.escape(text[i]))
        i+=1
    return ''.join(output)


def question_html(text: str) -> str:
    lines=text.splitlines()
    choices=[i for i,line in enumerate(lines) if re.match(r'^\s*[A-D][.)]?\s+\S',line)]
    ordered=[]
    for index in choices:
        current=lines[index].lstrip()[0]
        if ordered and current <= lines[ordered[-1]].lstrip()[0]:
            ordered=[]
        ordered.append(index)
    choices=ordered
    if len(choices)<2:
        return '<p>'+math_html(text or 'Question text has not been captured yet.')+'</p>'
    start=choices[0]
    result='<p>'+math_html('\n'.join(lines[:start]))+'</p>'
    for index,i in enumerate(choices):
        end=choices[index+1] if index+1<len(choices) else len(lines)
        match=re.match(r'^\s*([A-D])[.)]?\s+(.*)',lines[i])
        body=match[2]+('\n'+'\n'.join(lines[i+1:end]) if end>i+1 else '')
        result+='<table width="100%" cellspacing="0" cellpadding="13"><tr>'
        result+='<td width="40"><b style="color:#426e9b">'+match[1]+'</b></td><td>'+math_html(body)+'</td></tr></table><br>'
    return result
