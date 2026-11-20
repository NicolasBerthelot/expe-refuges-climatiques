// Extrait les styles MapLibre de Carte facile (https://github.com/fab-geocommuns/carte-facile, Apache-2.0)
// vers maquette/site/data/carte-facile.json, pour les embarquer dans la maquette sans bundler.
// Usage : npm i carte-facile@0.10.2 maplibre-gl && node scripts/build_styles_carte_facile.mjs
import { mapStyles } from 'carte-facile';
import fs from 'fs';
const out = {};
for (const k of ['simple', 'desaturated', 'aerial']) out[k] = mapStyles[k];
fs.writeFileSync(process.argv[2] || 'maquette/site/data/carte-facile.json', JSON.stringify(out));
console.log('Styles Carte facile :', Object.keys(out).join(', '));
