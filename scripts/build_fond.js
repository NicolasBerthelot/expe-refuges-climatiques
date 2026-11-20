const topo=require('topojson-client');
const w=require('world-atlas/countries-50m.json');
const fc=topo.feature(w,w.objects.countries);
const B=[-12,34,22,58];
const inb=r=>r.some(([x,y])=>x>B[0]&&x<B[2]&&y>B[1]&&y<B[3]);
const r3=v=>Math.round(v*1000)/1000;
const out=[];
for(const f of fc.features){
  const g=f.geometry; if(!g) continue;
  let polys=g.type==='Polygon'?[g.coordinates]:g.coordinates;
  polys=polys.filter(p=>inb(p[0]));
  if(!polys.length) continue;
  out.push({type:'Feature',properties:{fr:f.id==='250'?1:0,n:f.properties.name},geometry:{type:'MultiPolygon',coordinates:polys.map(p=>p.map(r=>r.map(([x,y])=>[r3(x),r3(y)])))}});
}
require('fs').writeFileSync(process.argv[2]||'maquette/site/data/fond.json',JSON.stringify({type:'FeatureCollection',features:out}));
console.log(out.length, out.map(f=>f.properties.n).join(', '));
