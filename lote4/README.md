# Lote 4: Instagram, noviembre 2026

Plan del mes: 18 publicaciones en Metricool (16 nuevas de este lote + 2 ya preparadas) y 2 cupos libres para noticias.

| Fecha | Hora | Pieza | Tema | Palabra clave (WhatsApp) |
|---|---|---|---|---|
| 3 nov | 12:00 | lote 2 · carrusel renta 2027 (borrador ya cargado) | ¿Le tocará declarar renta? | RENTA |
| 4 nov | 07:30 | `p01_equipo` | Marca: el equipo | — |
| 5 nov | 12:00 | `p02_s1-3` | Vencimientos de noviembre por NIT | CALENDARIO |
| 6 nov | 12:00 | lote 3 · reel Ley de Rescate (borrador: revisar antes) | Proyecto de reforma | REFORMA |
| 9 nov | 07:30 | `p04_sancion` | Sanciones por declarar tarde | — |
| 10 nov | 12:00 | `p05_manana` | Recordatorio: arrancan IVA y retención | — |
| 12 nov | 12:00 | `p06_s1-4` | 5 señales para cambiar de contador | DIAGNÓSTICO |
| 13 nov | 07:30 | `p07_plataforma` | Plataforma Axios | — |
| 17 nov | 07:30 | `p08_s1-4` | Planeación de renta antes del 31 dic | PLANEAR |
| 18 nov | 12:00 | `p09_exogena` | Exógena 2026 | EXÓGENA |
| 19 nov | 07:30 | `p10_revisor` | ¿Revisor fiscal en 2027? | REVISOR |
| 20 nov | 12:00 | `p17_saldo` | Devolución de saldos a favor | SALDO |
| 23 nov | 07:30 | `p11_ultima` | Última semana IVA y retención | — |
| 24 nov | 12:00 | `p12_s1-3` | Nómina de diciembre | NÓMINA |
| 25 nov | 07:30 | `p13_s1-3` | ¿Por qué Axios? | — |
| 26 nov | 12:00 | `p14_s1-3` | Régimen SIMPLE 2027 | SIMPLE |
| 27 nov | 07:30 | `p15_empresa` | Crear empresa en diciembre | EMPRESA |
| 30 nov | 12:00 | `p16_s1-3` | Vencimientos de diciembre | CALENDARIO |

Cupos libres sugeridos: la resolución de la UVT 2027 (la DIAN la publica entre mediados de noviembre y diciembre) y el avance de la Ley de Rescate en comisiones (primer debate previsto del 17 al 27 de noviembre).

## Fuentes de las fechas

- Calendario tributario 2026 (Decreto 2229 de 2023). Noviembre: IVA bimestral sep-oct, retención de octubre, INC y SIMPLE del 11 al 25 (festivos 2 y 16 de noviembre). Diciembre: retención de noviembre del 10 al 23 (festivo 8 de diciembre).
- Bogotá, Resolución SDH-000195: ReteICA 5.º bimestre el 20 nov; ICA bimestral sep-oct el 11 dic.
- Prima y dotación: arts. 306 y 230-232 CST. Cesantías: Ley 50 de 1990, art. 99, y Ley 52 de 1975.
- UVT 2026: $52.374 (Resolución DIAN 000238 de 2025).

## Archivos

- `fuente/noviembre.html`: todas las piezas (HTML + CSS de marca, fuentes Poppins del sitio).
- `fuente/render.js`: `node lote4/fuente/render.js lote4/fuente/noviembre.html lote4` exporta cada pieza a PNG 1080x1350.
- `plan.py` / `plan.json`: textos, textos alternativos, fechas y horas de cada publicación.
