# -*- coding: utf-8 -*-
"""
Diagnóstico: copia el panel a ../dashboard_prueba_<n> sin una página (y sin sus marcadores) para
comprobar si esa página es la que impide abrir/publicar el informe en Power BI Desktop.

    python probar_sin_pagina.py d29bdaf236bac4652495        # Campana de estimación
    python probar_sin_pagina.py list                         # lista las páginas
"""
import json, os, shutil, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
D = os.path.join('DS_Market.Report', 'definition')


def leer(p):
    return json.load(open(p, encoding='utf-8-sig'))


def escribir(p, j):
    json.dump(j, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


if len(sys.argv) < 2 or sys.argv[1] == 'list':
    pg = leer(os.path.join(AQUI, D, 'pages', 'pages.json'))
    for p in pg['pageOrder']:
        print(p, '|', leer(os.path.join(AQUI, D, 'pages', p, 'page.json'))['displayName'])
    sys.exit()

pid = sys.argv[1]
dest = os.path.join(os.path.dirname(AQUI), f'dashboard_prueba_{pid[:6]}')
if os.path.exists(dest):
    shutil.rmtree(dest)
shutil.copytree(AQUI, dest, ignore=shutil.ignore_patterns('probar_sin_pagina.py', '.pbi', 'cache.abf'))
pj = os.path.join(dest, D, 'pages', 'pages.json')
pg = leer(pj)
assert pid in pg['pageOrder'], 'página inexistente'
pg['pageOrder'].remove(pid)
if pg.get('activePageName') == pid:
    pg['activePageName'] = pg['pageOrder'][0]
escribir(pj, pg)
shutil.rmtree(os.path.join(dest, D, 'pages', pid))
# marcadores que apuntan a esa página
bdir = os.path.join(dest, D, 'bookmarks')
quitar = set()
for f in os.listdir(bdir):
    if f.endswith('.bookmark.json'):
        b = leer(os.path.join(bdir, f))
        if b.get('explorationState', {}).get('activeSection') == pid:
            quitar.add(b['name']); os.remove(os.path.join(bdir, f))
bj = os.path.join(bdir, 'bookmarks.json')
bm = leer(bj)
def limpiar(items):
    out = []
    for it in items:
        if it['name'] in quitar:
            continue
        if 'children' in it:
            it['children'] = [c for c in it['children'] if c not in quitar]
            if not it['children']:
                continue
        out.append(it)
    return out
bm['items'] = limpiar(bm['items'])
escribir(bj, bm)
print('Creado:', dest, '| marcadores quitados:', len(quitar))
print('Abre', os.path.join(dest, 'DS_Market.pbip'))
