# Design System: The Digital Heirloom

Framework para una experiencia genealógica premium. Trata la historia familiar como una exposición curada, no como una base de datos. Cada pantalla como una página de un archivo editorial de alta gama — organizado, autoritario, pero personal y táctil.

## Paleta de Colores

| Token | Hex | Uso |
|-------|-----|-----|
| `primary` | `#17341e` | Verde profundo principal |
| `primary_container` | `#2d4b33` | Contenedores primarios |
| `secondary` | `#78583e` | Acentos ámbar/madera |
| `secondary_container` | `#fdd2b1` | Botones secundarios "madera cálida" |
| `tertiary` | `#392d13` | Headlines, tinta envejecida |
| `surface` | `#fcf9f0` | Canvas principal (pergamino) |
| `surface_container` | `#f1eee5` | Sidebars, zonas de navegación |
| `surface_container_low` | `#f6f3ea` | Inputs, zonas secundarias |
| `surface_container_lowest` | `#ffffff` | Cards elevadas "impresión fotográfica" |
| `on_surface` | `#1c1c17` | Texto (nunca negro puro) |
| `on_primary` | `#ffffff` | Texto sobre primary |
| `outline_variant` | `#c2c8bf` | Ghost borders (20% opacity) |
| `error` | `#ba1a1a` | Errores |

## Tipografía

- **Display/Headlines**: Noto Serif — voz "Heritage", para nombres, épocas, storytelling
- **Body/Labels**: Manrope — voz "Utility", para fechas, lugares, citaciones
- **Títulos** en `tertiary` (#392d13) para simular tinta envejecida
- **Body** en `on_surface` (#1c1c17)

## Reglas clave

- **No-Line Rule**: Prohibidos los bordes 1px solid. Separar zonas con cambios de fondo
- **No negro puro**: Siempre on_surface (#1c1c17)
- **Bordes redondeados**: Mínimo rounded-sm (0.25rem), nunca squared
- **Sin divisores**: Usar 2rem de whitespace vertical
- **Glassmorphism**: Para elementos flotantes, backdrop-filter: blur(12px)
- **Asimetría intencional**: Headlines off-center, elementos que se solapan
- **Sombras ambientales**: box-shadow: 0 12px 40px rgba(28, 28, 23, 0.06)

## Componentes

- **Botones primarios**: primary filled, texto on_primary, rounded-md (0.75rem)
- **Botones secundarios**: secondary_container fondo, efecto "madera cálida"
- **Cards**: surface_container_lowest, rounded-sm, sin bordes
- **Inputs**: Fondo surface_container_low, en focus transición a surface_container_lowest
- **Timeline Node**: Punto primary con halo surface_variant, líneas dashed en outline_variant

## Spacing

Factor 3. Tokens principales: spacing-6 (2rem), spacing-10, spacing-12, spacing-16.
