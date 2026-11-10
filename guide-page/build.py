"""Build the guide page from head.html + body.html + script.js + ../industries.json.

    python3 guide-page/build.py      -> guide-page/internship-radar.html (the Claude artifact),
                                        docs/index.html (the public copy on GitHub Pages:
                                        https://buildingbrian.github.io/mba-internship-radar/)
                                        and guide-page/preview/index.html
    node guide-page/serve.js         -> preview at http://127.0.0.1:4130
"""
import json, os
P = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(P, '..', 'industries.json')))
data = json.dumps({'roles': d['roles'], 'industries': d['industries']}, ensure_ascii=False, separators=(',', ':'))
js = open(os.path.join(P, 'script.js')).read().replace('__DATA__', data)
head, body = open(os.path.join(P, 'head.html')).read(), open(os.path.join(P, 'body.html')).read()
html = head + body + '<script>\n' + js + '\n</script>\n'
open(os.path.join(P, 'internship-radar.html'), 'w').write(html)
shell = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
         '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif}[hidden]{display:none!important}</style></head><body>\n')
os.makedirs(os.path.join(P, 'preview'), exist_ok=True)
open(os.path.join(P, 'preview', 'index.html'), 'w').write(shell + html + '</body></html>\n')
# Standalone copy for GitHub Pages: a full document, so it opens for anyone with no Claude sign-in.
DESC = 'Free daily radar for MBA internships: about 165 company job boards plus your LinkedIn, Handshake and CMG alerts, by email, iMessage or a Google Sheet.'
BASE = ('<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0;padding:0}img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>\n')
page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        f'<meta name="description" content="{DESC}">\n'
        '<meta property="og:title" content="Internship Radar">\n'
        f'<meta property="og:description" content="{DESC}">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:url" content="https://buildingbrian.github.io/mba-internship-radar/">\n'
        + BASE + head + '</head>\n<body>\n' + body + '<script>\n' + js + '\n</script>\n</body>\n</html>\n')
docs = os.path.join(P, '..', 'docs')
os.makedirs(docs, exist_ok=True)
open(os.path.join(docs, 'index.html'), 'w').write(page)
open(os.path.join(docs, '.nojekyll'), 'w').write('')
print('built', len(html), 'bytes;', 'docs/index.html', len(page), 'bytes')
