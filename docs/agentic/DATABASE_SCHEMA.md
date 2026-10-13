# Esquema de datos: TurnoFacil

- Estado: aprobado por el Founder (2026-10-13)
- Fecha: 2026-10-13

Nombres en inglés porque son código. Todas las tablas tienen `id` autoincremental. Fechas y horas en UTC.

## Relaciones
```
User 1──1 Business 1──N Service
                   1──N Professional 1──N WorkingHours
                   1──N Appointment N──1 Professional
                                    N──1 Service
```

## User (`accounts`)
| Campo | Tipo | Reglas |
|---|---|---|
| email | texto | único, es el identificador de inicio de sesión |
| password | hash | gestionado por Django |
| is_active | booleano | |
| date_joined | fecha y hora | |

## Business (`businesses`)
| Campo | Tipo | Reglas |
|---|---|---|
| owner | FK a User | único (un negocio por usuario) |
| name | texto | obligatorio |
| slug | texto | único; se genera del nombre y forma el link público `/b/<slug>/` |
| created_at | fecha y hora | |

## Service
| Campo | Tipo | Reglas |
|---|---|---|
| business | FK a Business | |
| name | texto | obligatorio |
| duration_minutes | entero | mayor a 0 (restricción en la base) |
| is_active | booleano | los servicios se desactivan, no se borran |

## Professional
| Campo | Tipo | Reglas |
|---|---|---|
| business | FK a Business | |
| name | texto | obligatorio |
| is_active | booleano | los profesionales se desactivan, no se borran |

## WorkingHours
Una fila por tramo de atención. Un día puede tener más de un tramo (horario cortado).

| Campo | Tipo | Reglas |
|---|---|---|
| professional | FK a Professional | |
| weekday | entero | 0 (lunes) a 6 (domingo) |
| start_time | hora | |
| end_time | hora | mayor a `start_time` (restricción en la base) |

Los tramos de un mismo profesional y día no pueden solaparse (validación en la app).

## Appointment (`bookings`)
| Campo | Tipo | Reglas |
|---|---|---|
| business | FK a Business | |
| professional | FK a Professional | no se puede borrar un profesional con turnos |
| service | FK a Service | no se puede borrar un servicio con turnos |
| customer_name | texto | obligatorio |
| customer_phone | texto | obligatorio |
| customer_email | texto | obligatorio si `source` es `online`; opcional si es `manual` |
| start_at | fecha y hora | |
| end_at | fecha y hora | `start_at` más la duración del servicio al momento de reservar |
| status | texto | `confirmed` o `cancelled` |
| source | texto | `online` (página pública) o `manual` (panel) |
| manage_token | texto | único, aleatorio; forma el link de gestión `/t/<token>/` |
| reminder_due_at | fecha y hora, opcional | `start_at` menos 24 h; vacío si no corresponde recordatorio |
| reminder_sent_at | fecha y hora, opcional | marca de recordatorio enviado |
| created_at, updated_at | fecha y hora | |
| cancelled_at | fecha y hora, opcional | |

### Restricciones
- `end_at` mayor a `start_at`.
- **Sin superposición:** restricción de exclusión sobre (`professional`, rango `start_at`–`end_at`) solo para
  turnos `confirmed`. Requiere la extensión `btree_gist` de PostgreSQL, que se activa en una migración.
- El profesional y el servicio del turno deben pertenecer al mismo negocio que el turno (validación en la app).

### Índices
- (`business`, `start_at`) para la agenda del panel.
- `reminder_due_at` para el comando de recordatorios.

## Notas
- Guardar `end_at` en el turno hace que editar la duración de un servicio no altere los turnos ya tomados.
- Los turnos cancelados se conservan con `status = cancelled`; no se borran.
- Los turnos manuales sin email no reciben confirmación ni recordatorio.
