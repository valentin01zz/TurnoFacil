# Rutas HTTP: TurnoFacil

- Estado: aprobado por el Founder (2026-10-13)
- Fecha: 2026-10-13

La app renderiza HTML en el servidor: no hay una API JSON separada. Este documento es el contrato de rutas.
Cada ruta lleva tests. Todos los `POST` validan en el backend y exigen token CSRF.

Cambio respecto de la versión aprobada (2026-10-16): la ruta `/b/<slug>/slots/` se reemplazó por parámetros
de la misma página de reservas. Funciona sin JavaScript y es una ruta menos; el comportamiento para el cliente
es el mismo salvo que la página se recarga al pedir horarios.

## Públicas (sin sesión)
| Método | Ruta | Qué hace | Historia |
|---|---|---|---|
| GET | `/` | Presentación mínima con accesos a registro e ingreso | |
| GET | `/b/<slug>/` | Página de reservas: servicio, profesional (si hay más de uno) y día. Con los parámetros `service`, `professional` y `date` muestra además los horarios libres y el formulario de datos | HU-04 |
| POST | `/b/<slug>/book/` | Crea el turno y envía la confirmación. Redirige a `/t/<token>/` | HU-04, HU-05 |
| GET | `/t/<token>/` | Detalle del turno con acciones de reprogramar y cancelar | HU-05 |
| GET, POST | `/t/<token>/reschedule/` | Elegir nuevo horario y confirmar | HU-06 |
| POST | `/t/<token>/cancel/` | Cancela el turno | HU-07 |

Respuestas esperadas:
- `slug` inexistente o token inválido: 404 con "no encontrado", sin datos.
- Negocio sin servicios o sin profesionales activos: la página indica que todavía no toma reservas.
- Horario ocupado al confirmar: se vuelve al formulario con el mensaje "ese horario se acaba de ocupar".
- Reprogramar o cancelar con menos de 2 horas, o sobre un turno pasado: se rechaza con un mensaje para contactar al negocio.
- Cancelar un turno ya cancelado: se informa que ya estaba cancelado, sin error.

## Cuenta
| Método | Ruta | Qué hace | Historia |
|---|---|---|---|
| GET, POST | `/signup/` | Registro: nombre del negocio, email, contraseña. Crea usuario y negocio | HU-01 |
| GET, POST | `/login/` | Ingreso con email y contraseña | HU-01 |
| POST | `/logout/` | Cierra la sesión | HU-01 |
| GET, POST | `/password-reset/…` | Recuperación de contraseña (vistas de Django) | |

## Panel (requiere sesión; solo datos del negocio propio)
| Método | Ruta | Qué hace | Historia |
|---|---|---|---|
| GET | `/panel/` | Agenda del día. Parámetros: `date`, `professional`. Muestra el link público | HU-01, HU-09 |
| GET | `/panel/services/` | Lista de servicios | HU-02 |
| GET, POST | `/panel/services/new/` | Crear servicio | HU-02 |
| GET, POST | `/panel/services/<id>/edit/` | Editar o desactivar servicio | HU-02 |
| GET | `/panel/professionals/` | Lista de profesionales | HU-03 |
| GET, POST | `/panel/professionals/new/` | Crear profesional con sus horarios | HU-03 |
| GET, POST | `/panel/professionals/<id>/edit/` | Editar, cambiar horarios o desactivar | HU-03 |
| GET, POST | `/panel/appointments/new/` | Cargar un turno a mano | HU-10 |
| GET, POST | `/panel/appointments/<id>/reschedule/` | Reprogramar un turno | HU-10 |
| POST | `/panel/appointments/<id>/cancel/` | Cancelar un turno | HU-10 |

Respuestas esperadas:
- Sin sesión: redirige a `/login/`.
- `<id>` de otro negocio: 404.
- Turno manual superpuesto con otro del mismo profesional: se rechaza con un mensaje claro.
- El panel puede reprogramar y cancelar sin el límite de 2 horas (ese límite aplica al cliente).

## Tarea programada
| Comando | Frecuencia | Qué hace | Historia |
|---|---|---|---|
| `python manage.py send_reminders` | cada 15 minutos | Envía los recordatorios vencidos y los marca como enviados | HU-08 |
