"""Build the guide page (published as a Claude artifact) from head.html + body.html + script.js + ../industries.json.

    python3 guide-page/build.py      -> guide-page/internship-radar.html and guide-page/preview/index.html
    node guide-page/serve.js         -> preview at http://127.0.0.1:4130
"""
import json, os
P = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(P, '..', 'industries.json')))
data = json.dumps({'roles': d['roles'], 'industries': d['industries']}, ensure_ascii=False, separators=(',', ':'))
js = open(os.path.join(P, 'script.js')).read().replace('__DATA__', data)
html = open(os.path.join(P, 'head.html')).read() + open(os.path.join(P, 'body.html')).read() + '<script>\n' + js + '\n</script>\n'
open(os.path.join(P, 'internship-radar.html'), 'w').write(html)
shell = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
         '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif}[hidden]{display:none!important}</style></head><body>\n')
os.makedirs(os.path.join(P, 'preview'), exist_ok=True)
open(os.path.join(P, 'preview', 'index.html'), 'w').write(shell + html + '</body></html>\n')
print('built', len(html), 'bytes')
