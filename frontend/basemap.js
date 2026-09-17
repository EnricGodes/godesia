// Basemap propio de Godesia: teselas vectoriales (OpenFreeMap, sin API key)
// pintadas en vivo con los colores del design system y solo con las capas que
// aportan algo — tierra, agua, verde, carreteras y nombres de población.
//
// Por qué vectorial y no teselas de imagen: las de imagen vienen con su propia
// paleta (la gris de Esri) y, al ser JPEG, dejan costuras visibles en las zonas
// planas como el mar. Aquí el mar es UN color liso dibujado en el navegador:
// ni líneas, ni juntas, ni relieve, ni fronteras marítimas, ni POIs.
//
// Requiere maplibre-gl + @maplibre/maplibre-gl-leaflet en la página. Si no
// están (o el navegador no tiene WebGL), cae a las teselas grises de Esri.

const GodesiaBasemap = (() => {
    // Paleta del design system (ver tailwind.config de cada página)
    const LAND = '#f6f3ea';   // surface-container-low
    const WATER = '#d4e0d3';  // sage: primary-container rebajado
    const GREEN = '#e7ede0';  // parques y bosque
    const ROAD = '#ffffff';   // vías principales
    const ROAD_MINOR = '#ffffff';  // mismo blanco: la jerarquía la marca el grosor
    const ROAD_CASING = '#e7e3d7';
    const LABEL = '#2D4B33';  // primary
    const LABEL_HALO = '#fcf9f0';

    const ATTRIBUTION =
        '© <a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> · ' +
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

    // Nombre en el idioma de la página, con caída al nombre local.
    function nameField() {
        const lang = (document.documentElement.lang || 'es').slice(0, 2);
        return ['coalesce', ['get', 'name:' + lang], ['get', 'name:latin'], ['get', 'name']];
    }

    function style() {
        return {
            version: 8,
            glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
            sources: {
                omt: { type: 'vector', url: 'https://tiles.openfreemap.org/planet' },
            },
            layers: [
                { id: 'land', type: 'background', paint: { 'background-color': LAND } },
                {
                    id: 'green', type: 'fill', source: 'omt', 'source-layer': 'landcover',
                    filter: ['in', ['get', 'class'], ['literal', ['wood', 'grass', 'park']]],
                    paint: { 'fill-color': GREEN },
                },
                {
                    id: 'park', type: 'fill', source: 'omt', 'source-layer': 'park',
                    paint: { 'fill-color': GREEN },
                },
                {
                    id: 'water', type: 'fill', source: 'omt', 'source-layer': 'water',
                    paint: { 'fill-color': WATER },
                },
                // Trazado blanco con un filete cálido: legible sin llamar la atención.
                {
                    id: 'road-casing', type: 'line', source: 'omt', 'source-layer': 'transportation',
                    minzoom: 11,
                    filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary']]],
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: {
                        'line-color': ROAD_CASING,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 2, 14, 4.5, 18, 12],
                    },
                },
                {
                    id: 'road-minor', type: 'line', source: 'omt', 'source-layer': 'transportation',
                    minzoom: 13,
                    filter: ['in', ['get', 'class'], ['literal', ['secondary', 'tertiary', 'minor', 'service']]],
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: {
                        'line-color': ROAD_MINOR,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 13, 0.8, 16, 3, 19, 9],
                    },
                },
                {
                    id: 'road', type: 'line', source: 'omt', 'source-layer': 'transportation',
                    filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary']]],
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: {
                        'line-color': ROAD,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.5, 11, 1.4, 14, 3, 18, 9],
                    },
                },
                // Nombres de calle solo a pie de calle (es lo que se busca en el
                // mapa de domicilios); en gris, para no competir con las poblaciones.
                {
                    id: 'street-name', type: 'symbol', source: 'omt',
                    'source-layer': 'transportation_name', minzoom: 15,
                    layout: {
                        'text-field': ['get', 'name'],
                        'text-font': ['literal', ['Noto Sans Regular']],
                        'text-size': 11,
                        'symbol-placement': 'line',
                        'text-max-angle': 30,
                        'text-padding': 4,
                    },
                    paint: {
                        'text-color': '#727971',
                        'text-halo-color': LABEL_HALO,
                        'text-halo-width': 1.4,
                    },
                },
                // Nombres de población: los pueblos pequeños y los barrios solo
                // aparecen cuando ya se ha hecho zoom, para no llenar la vista.
                {
                    id: 'place', type: 'symbol', source: 'omt', 'source-layer': 'place',
                    filter: ['any',
                        ['in', ['get', 'class'], ['literal', ['city', 'town']]],
                        ['all', ['==', ['get', 'class'], 'village'], ['>=', ['zoom'], 11]],
                        ['all', ['==', ['get', 'class'], 'suburb'], ['>=', ['zoom'], 13]],
                    ],
                    layout: {
                        'text-field': nameField(),
                        'text-font': ['case', ['==', ['get', 'class'], 'city'],
                            ['literal', ['Noto Sans Bold']], ['literal', ['Noto Sans Regular']]],
                        'text-size': ['interpolate', ['linear'], ['zoom'], 6, 10, 12, 13, 16, 15],
                        'text-max-width': 8,
                        'text-padding': 6,
                    },
                    paint: {
                        'text-color': LABEL,
                        'text-halo-color': LABEL_HALO,
                        'text-halo-width': 1.6,
                    },
                },
            ],
        };
    }

    function hasWebGL() {
        try {
            const c = document.createElement('canvas');
            return !!(c.getContext('webgl2') || c.getContext('webgl'));
        } catch (e) {
            return false;
        }
    }

    // Plan B: canvas gris de Esri (sin API key). Solo llega a z16 nativo, de ahí
    // maxNativeZoom para que escale en vez de servir "Map data not yet available".
    function raster(map) {
        const esri = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/';
        const opts = { maxNativeZoom: 16, maxZoom: 19 };
        return L.layerGroup([
            L.tileLayer(esri + 'World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
                ...opts,
                attribution: 'Tiles © <a href="https://www.esri.com/">Esri</a>',
                className: 'tiles-muted',
            }),
            L.tileLayer(esri + 'World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', opts),
        ]).addTo(map);
    }

    // Devuelve SIEMPRE una capa que se puede quitar con .remove(), para las
    // páginas que alternan de base (cementerios: general ↔ satélite).
    function add(map) {
        if (window.maplibregl && L.maplibreGL && hasWebGL()) {
            try {
                return L.maplibreGL({ style: style(), attribution: ATTRIBUTION }).addTo(map);
            } catch (e) {
                /* cae al plan B */
            }
        }
        return raster(map);
    }

    return { add, style, ATTRIBUTION };
})();
