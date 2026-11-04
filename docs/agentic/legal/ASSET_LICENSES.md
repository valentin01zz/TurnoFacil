# Inventario de activos y licencias: TurnoFacil

Fecha: 2026-10-24 · Commit revisado: `33cce4f` · Revisó: Legal & Compliance Agent (NEXORA)

## Recursos visuales y de contenido
| Recurso | Tipo | Ubicación | Autor o titular | Fuente | Licencia | Uso comercial | Atribución | Restricciones | Evidencia | Estado | Riesgo y acción |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Bricolage Grotesque (variable) | Tipografía | `static/fonts/BricolageGrotesque-Variable.ttf` (servida desde el sitio desde 2026-10-24) | The Bricolage Grotesque Project Authors | `github.com/google/fonts`, `ofl/bricolagegrotesque` | SIL OFL 1.1 | Sí | No en la web | No vender la fuente sola; el nombre reservado no se usa en versiones modificadas (no se modificó) | `static/fonts/BricolageGrotesque-OFL.txt` | ACREDITADO | Bajo. La licencia viaja junto al archivo |
| Hanken Grotesk (variable, sin itálica) | Tipografía | `static/fonts/HankenGrotesk-Variable.ttf` (ídem) | The Hanken Grotesk Project Authors | `github.com/google/fonts`, `ofl/hankengrotesk` | SIL OFL 1.1 | Sí | No en la web | Ídem | `static/fonts/HankenGrotesk-OFL.txt` | ACREDITADO | Bajo. Ídem |
| Íconos SVG (calendar, star, mail, etc.) | Íconos | `templates/_icon.html` | Creados en el proyecto (trazos geométricos simples) | Propios | No aplica | Sí | No | — | Código en el repo; sin registro de autoría ni de si se generaron con IA | PENDIENTE | Bajo. Confirmar con el Founder el origen y anotarlo |
| Logo TurnoFacil (ícono calendario + texto) | Logo/marca | `templates/base.html` | [COMPLETAR] | Propio | No aplica | — | — | — | Sin búsqueda de marca | PENDIENTE | Ver H14 del `LEGAL_REVIEW` |
| Textos del sitio | Texto | `templates/` | Founder / agentes NEXORA | Propios | No aplica | Sí | No | — | Repo | ACREDITADO | — |
| Fotos, videos, audios | — | No hay | — | — | — | — | — | — | `static/` solo tiene CSS, JS y las dos fuentes | N/A | — |

Material de marketing (posts y reel): vive en `TurnoFacil/marketing`, fuera de este inventario; se inventaría
aparte si se publica con música o imágenes de terceros.

## Dependencias de código
Fuente: `importlib.metadata` sobre `.venv` (2026-10-24).

| Paquete | Versión | Licencia | Uso | Obligaciones | Estado |
|---|---|---|---|---|---|
| Django | 5.2.18 | BSD-3-Clause | Servicio (no se distribuye) | Ninguna al no distribuir | ACREDITADO |
| psycopg / psycopg-binary | 3.3.6 | LGPL-3.0-only | Servicio, sin modificar | Al no distribuir, ninguna práctica; si algún día se distribuye la app, cumplir LGPL | ACREDITADO |
| gunicorn | 26.2.0 | MIT | Servicio | Ninguna al no distribuir | ACREDITADO |
| whitenoise | 6.12.0 | MIT | Servicio | Ídem | ACREDITADO |
| asgiref | 3.12.1 | BSD-3-Clause | Dependencia de Django | Ídem | ACREDITADO |
| sqlparse | 0.6.0 | BSD | Dependencia de Django | Ídem | ACREDITADO |
| tzdata | 2026.5 | Apache-2.0 | Zonas horarias | Ídem | ACREDITADO |
| ruff (solo desarrollo) | — | MIT | Desarrollo | Ninguna | ACREDITADO |

## Código de terceros y recursos generados con IA
| Fragmento o recurso | Ubicación | Origen | Condiciones | Estado |
|---|---|---|---|---|
| Código de la app | Todo el repo | Founder con asistencia de agentes de IA (Claude Code) | Titularidad del código asistido por IA: asunto para abogado si se vende o licencia el producto | PENDIENTE |
