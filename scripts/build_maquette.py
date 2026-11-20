"""Génère les données de la maquette et la version autonome (un seul fichier HTML).

Usage :
  python scripts/build_maquette.py donnees/refuges_climatiques_AAAA-MM-JJ.gpkg <export_tout_gogocarto.csv>

Produit :
  maquette/site/data/{refuges,potentiels,departements}.json
  maquette/site/index.html            (version servie par un serveur web, lit data/*.json)
  maquette/refuges_climatiques_maquette.html  (version autonome, ouvrable par double-clic)
Prérequis : pandas, geopandas, pyogrio, scipy ; maquette/site/fonts.css, maplibre-gl.css, data/fond.json
et data/carte-facile.json
(voir README pour leur génération).
"""
import sys, json, re, pathlib, numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from build_gpkg import load

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / 'maquette' / 'site'
TY = ['espaces verts','espaces publics extérieurs','sport et loisirs','culturel','lieu de culte','équipement de quartier','autre']
FRL = ['très frais','fraîcheur modérée','faible fraîcheur']
OML = ['très ombragé','moyennement ombragé','peu ombragé','non concerné']
POT = ['espace vert','sport et loisirs','culturel','équipement de quartier','autre']
QA = ['qa_fraicheur_multiple','qa_ombrage_multiple','qa_geoloc_suspecte','qa_sans_adresse','qa_doublon_refuge','qa_sans_typologie']

def nn(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    return v

def dep_of(c):
    if not isinstance(c, str): return None
    if c.startswith('97'): return c[:3]
    if c.startswith('20'): return '2A' if c[:3] in ('200', '201') else '2B'
    return c[:2]

def main(gpkg, tout_csv):
    r = gpd.read_file(gpkg, layer='refuges_climatiques')
    p = gpd.read_file(gpkg, layer='espaces_refuges_potentiels')
    deps = json.load(open(ROOT / 'scripts' / 'ref' / 'departements.json', encoding='utf-8'))
    # département : code postal, sinon point le plus proche de l'export complet dont le département est connu
    t = load(tout_csv); known = t[t.dep.notna()]
    tree = cKDTree(np.c_[known.lat.values, known.lon.values * np.cos(np.radians(46.5))])
    r['dep'] = r.code_postal.map(dep_of); r['dep_est'] = r.dep.isna()
    if r.dep_est.any():
        m = r.dep_est
        _, ix = tree.query(np.c_[r[m].geometry.y, r[m].geometry.x * np.cos(np.radians(46.5))])
        r.loc[m, 'dep'] = known.dep.values[ix]
    recs = []
    for _, x in r.iterrows():
        q = [k for k in QA if bool(x[k])] + (['qa_doublon_potentiel'] if nn(x.qa_doublon_potentiel) else [])
        rec = {'i': x.id_source, 'n': x.nom, 'd': nn(x.description),
               't': [TY.index(v) for v in (nn(x.typologie) or '').split(' | ') if v in TY], 'tp': nn(x.type_precision),
               'f': FRL.index(x.fraicheur_niveau), 'fm': bool(x.qa_fraicheur_multiple),
               'p': [int(x.periode_matin), int(x.periode_apres_midi), int(x.periode_soir)],
               'o': [OML.index(v) for v in (nn(x.ombrage) or '').split(' | ') if v in OML],
               'e': [int(x.eau_etendue), int(x.eau_jeux), int(x.eau_fontaine)], 'ep': nn(x.eau_potable),
               's': [int(x.service_enfants), int(x.service_assises), int(x.service_toilettes), int(x.service_gratuit), int(x.service_climatise)],
               'pmr': nn(x.accessibilite_pmr), 'ae': nn(x.autres_equipements), 'h': nn(x.horaires_osm), 'hp': nn(x.horaires_precision),
               'w': nn(x.site_internet), 'tel': nn(x.telephone), 'img': nn(x.image_url), 'a': nn(x.adresse), 'cp': nn(x.code_postal),
               'c': nn(x.commune), 'dep': x.dep, 'de': bool(x.dep_est), 'src': nn(x.source_import), 'st': x.statut_source,
               'mod': x.moderation, 'dc': str(x.date_creation)[:10], 'dm': str(x.date_maj)[:10], 'q': q,
               'tw': nn(x.qa_doublon_potentiel), 'x': round(x.geometry.x, 5), 'y': round(x.geometry.y, 5)}
        recs.append({k: v for k, v in rec.items() if v not in (None, [], False) or k in ('f', 'p', 's', 'e', 't')})
    pots = [[round(x, 5), round(y, 5), i, n if isinstance(n, str) else '', POT.index(c) if c in POT else -1]
            for x, y, i, n, c in zip(p.geometry.x, p.geometry.y, p.id_source, p.nom, p.categorie_potentiel)]
    D = SITE / 'data'; D.mkdir(parents=True, exist_ok=True)
    json.dump(recs, open(D / 'refuges.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    (D / 'potentiels.json').write_text('[\n' + ',\n'.join(json.dumps(z, ensure_ascii=False, separators=(',', ':')) for z in pots) + '\n]', encoding='utf-8')
    json.dump({k: deps[k] for k in sorted(set(r.dep)) if k in deps}, open(D / 'departements.json', 'w', encoding='utf-8'), ensure_ascii=False)
    # page servie + version autonome
    src = (ROOT / 'maquette' / 'src' / 'index.src.html').read_text(encoding='utf-8')
    page = src.replace('/*ICONS*/null', (ROOT / 'maquette' / 'src' / 'icons.json').read_text(encoding='utf-8'))
    (SITE / 'index.html').write_text(page, encoding='utf-8')
    st = page.replace('<link rel="stylesheet" href="fonts.css">', '<style>' + (SITE / 'fonts.css').read_text(encoding='utf-8') + '</style>')
    st = st.replace('<link rel="stylesheet" href="maplibre-gl.css">', '<style>' + (SITE / 'maplibre-gl.css').read_text(encoding='utf-8') + '</style>')
    blk = ''.join(f'<script type="application/json" id="d-{k}">'
                  + json.dumps(json.load(open(D / f'{k}.json', encoding='utf-8')), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
                  + '</script>\n' for k in ('refuges', 'departements', 'fond', 'carte-facile', 'potentiels'))
    st = st.replace('<script src="https://unpkg.com/maplibre-gl', blk + '<script src="https://unpkg.com/maplibre-gl', 1)
    (ROOT / 'maquette' / 'refuges_climatiques_maquette.html').write_text(st, encoding='utf-8')
    print(f'{len(recs)} refuges, {len(pots)} espaces potentiels, {r.dep_est.sum()} départements estimés')

if __name__ == '__main__':
    main(*sys.argv[1:3])
