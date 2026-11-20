"""Construit un GeoPackage normalisé à partir des exports GoGoCarto « Refuges climatiques ».
Usage : python build_gpkg.py <export_refuges.csv> <export_tout.csv> <sortie.gpkg>
Dépendances : pandas, geopandas, pyogrio, scipy
"""
import sys, re, unicodedata, numpy as np, pandas as pd, geopandas as gpd
from difflib import SequenceMatcher
from scipy.spatial import cKDTree

STATUT={'1':'validé','2':'validé collaborativement','3':'ajouté par admin','4':'modifié par admin','5':'modifié par le propriétaire','7':'importé','-1':'modification en attente','0':'ajout en attente','-4':'supprimé','-6':'doublon supprimé'}
MODER={'0':'ok','1':'signalement','2':'votes en conflit','3':'en attente trop longue','4':'doublon potentiel','-1':'sans catégorie','-2':'erreur géoloc'}
FR={'38':'très frais','39':'fraîcheur modérée','40':'faible fraîcheur'}
OM={'87':'très ombragé','88':'moyennement ombragé','89':'peu ombragé','289':'non concerné'}
TY={'96':'espaces verts','97':'espaces publics extérieurs','98':'sport et loisirs','99':'culturel','100':'lieu de culte','101':'équipement de quartier','102':'autre'}
POT={'20':'espace vert','53':'sport et loisirs','22':'culturel','23':'équipement de quartier','24':'autre'}
EP={'94':'oui','95':'non','290':'non renseigné'}
RANK={'38':'très frais','39':'fraîcheur modérée','40':'faible fraîcheur'}

def s(v): return v.strip() if isinstance(v,str) and v.strip() else None
def ids(v): return set(v.split(',')) if isinstance(v,str) else set()
def pick(x,m): v=[m[i] for i in m if i in x]; return ' | '.join(v) if v else None
def norm(v):
    v=unicodedata.normalize('NFKD',str(v).lower()); v=''.join(c for c in v if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',v).strip()
def cp_of(row):
    for v in (row.postalCode,row.fullAddress,row.address):
        if isinstance(v,str):
            m=re.search(r'\b(\d{5})\b',v)
            if m: return m.group(1)
def dep_of(c):
    if not isinstance(c,str): return None
    if c.startswith('97'): return c[:3]
    if c.startswith('20'): return '2A' if c[:3] in ('200','201') else '2B'
    return c[:2]
def adr(row):
    if s(row.fullAddress): return s(row.fullAddress)
    a=' '.join(x for x in (row.streetNumber,row.streetAddress) if s(x))
    c=' '.join(x for x in (row.postalCode,row.addressLocality) if s(x))
    return s(', '.join(x for x in (a,c) if x))
def xy(d): return np.c_[np.radians(d.lat)*6371000, np.radians(d.lon)*6371000*np.cos(np.radians(46.5))]

def load(p):
    d=pd.read_csv(p,dtype=str,low_memory=False)
    d['lat']=d.latitude.astype(float); d['lon']=d.longitude.astype(float)
    d['ids']=d.categories_ids.map(ids); d['cp']=d.apply(cp_of,axis=1); d['dep']=d.cp.map(dep_of)
    return d

def main(f_ref,f_tout,out):
    r,t=load(f_ref),load(f_tout)
    dead={'-6','-4'}
    # contrôle géoloc : distance à la médiane du département (calculée sur l'export complet)
    med=t.groupby('dep')[['lat','lon']].median().rename(columns={'lat':'lat_m','lon':'lon_m'})
    r=r.join(med,on='dep')
    a,b,c,e=map(np.radians,(r.lat,r.lon,r.lat_m,r.lon_m))
    r['dist']=6371*2*np.arcsin(np.sqrt(np.sin((c-a)/2)**2+np.cos(a)*np.cos(c)*np.sin((e-b)/2)**2))
    live=r[~r.status.isin(dead)].copy(); live['nn']=live.name.map(norm)
    # doublons refuge-refuge : même nom (similarité >=0,95) à moins de 2 km
    tree=cKDTree(xy(live)); dup=set(); N=live.nn.values; I=live.id.values
    for i,j in tree.query_pairs(2000):
        if SequenceMatcher(None,N[i],N[j]).ratio()>=0.95:
            dup|={I[i],I[j]}
    # refuge posé à côté de son espace potentiel (<100 m, nom proche >=0,75)
    tp=t[(~t.id.isin(r.id))&(~t.status.isin(dead))].copy(); tp['nn']=tp.name.map(norm)
    pt=cKDTree(xy(tp)); twin={}
    for rid,nn,p in zip(live.id,live.nn,xy(live)):
        for j in pt.query_ball_point(p,100):
            if SequenceMatcher(None,nn,tp.nn.iat[j]).ratio()>=0.75: twin.setdefault(rid,tp.id.iat[j])
    L=live
    g=pd.DataFrame({
     'id_source':L.id,'nom':L.name.map(s),'description':L.text_1745486587494.map(s),
     'typologie':L.ids.map(lambda x:pick(x,TY)),'type_precision':L.text_1750080045704.map(s),
     'categorie_potentiel':L.ids.map(lambda x:pick(x,POT)),
     'ressenti_fraicheur':L.ids.map(lambda x:pick(x,FR)),
     'fraicheur_niveau':L.ids.map(lambda x:next((RANK[k] for k in ('38','39','40') if k in x),None)),
     'periode_matin':L.ids.map(lambda x:'279' in x),'periode_apres_midi':L.ids.map(lambda x:'280' in x),'periode_soir':L.ids.map(lambda x:'281' in x),
     'ombrage':L.ids.map(lambda x:pick(x,OM)),
     'eau_etendue':L.ids.map(lambda x:'90' in x),'eau_jeux':L.ids.map(lambda x:'91' in x),'eau_fontaine':L.ids.map(lambda x:'92' in x),
     'eau_potable':L.ids.map(lambda x:pick(x,EP)),
     'service_enfants':L.ids.map(lambda x:'47' in x),'service_assises':L.ids.map(lambda x:'26' in x),'service_toilettes':L.ids.map(lambda x:'56' in x),
     'service_gratuit':L.ids.map(lambda x:'48' in x),'service_climatise':L.ids.map(lambda x:'277' in x),
     'accessibilite_pmr':L.text_1785933346814.map(s),'autres_equipements':L.autres_espaces.map(s),
     'horaires_osm':L.openHours.map(s),'horaires_precision':L.text_1745573526038.map(s),
     'site_internet':L.site_internet.map(s),'telephone':L.text_1745483639626.map(s),
     'image_url':L.images.map(lambda v:s(v.split(',')[0]) if isinstance(v,str) else None),
     'adresse':L.apply(adr,axis=1),'code_postal':L.cp,'commune':L.addressLocality.map(s),
     'source_import':L.source.map(s),'id_ref_externe':L.oldId.map(s),'osm_url':L.osm_url.map(s),
     'statut_source':L.status.map(STATUT),'moderation':L.moderationState.map(MODER),
     'date_creation':pd.to_datetime(L.createdAt),'date_maj':pd.to_datetime(L.updatedAt)})
    g['qa_fraicheur_multiple']=L.ids.map(lambda x:len(x&set(FR))>1)
    g['qa_ombrage_multiple']=L.ids.map(lambda x:len(x&{'87','88','89'})>1)
    g['qa_geoloc_suspecte']=(L.dist>120).fillna(False)
    g['qa_sans_adresse']=g.adresse.isna()
    g['qa_doublon_refuge']=g.id_source.isin(dup)
    g['qa_doublon_potentiel']=g.id_source.map(twin)
    g['qa_sans_typologie']=g.typologie.isna()
    g=gpd.GeoDataFrame(g,geometry=gpd.points_from_xy(L.lon,L.lat),crs=4326)
    pot=gpd.GeoDataFrame({'id_source':tp.id,'nom':tp.name.map(s),'categorie_potentiel':tp.ids.map(lambda x:pick(x,POT)),
     'adresse':tp.apply(adr,axis=1),'source_import':tp.source.map(s),'id_ref_externe':tp.oldId.map(s),
     'osm_url':tp.osm_url.map(s),'site_internet':tp.site_internet.map(s),
     'statut_source':tp.status.map(STATUT),'moderation':tp.moderationState.map(MODER),
     'date_creation':pd.to_datetime(tp.createdAt),'date_maj':pd.to_datetime(tp.updatedAt)},
     geometry=gpd.points_from_xy(tp.lon,tp.lat),crs=4326)
    g.to_file(out,layer='refuges_climatiques',driver='GPKG')
    pot.to_file(out,layer='espaces_refuges_potentiels',driver='GPKG')
    print(f"{len(g)} refuges, {len(pot)} espaces potentiels -> {out}")
    print(g.filter(like='qa_').apply(lambda c:int(c.sum()) if c.dtype==bool else int(c.notna().sum())).to_string())

if __name__=='__main__':
    main(*sys.argv[1:4])
