# Backlog: TurnoFacil

Orden sugerido de construcción. El detalle de cada historia está en `USER_STORIES.md` y `ACCEPTANCE_CRITERIA.md`.

## MVP
Estado: las 10 historias están implementadas y con tests (2026-10-18). Falta el QA gate y el primer deploy.

| Orden | Historia | Depende de |
|---|---|---|
| 1 | HU-01 Registro del negocio | Arquitectura y stack aprobados |
| 2 | HU-02 Servicios | HU-01 |
| 3 | HU-03 Profesionales y horarios | HU-01 |
| 4 | HU-04 Reservar un turno | HU-02, HU-03 |
| 5 | HU-09 Ver la agenda | HU-04 |
| 6 | HU-05 Confirmación por email | HU-04 |
| 7 | HU-07 Cancelar | HU-05 |
| 8 | HU-06 Reprogramar | HU-05 |
| 9 | HU-10 Gestionar turnos desde el panel | HU-09 |
| 10 | HU-08 Recordatorio por email | HU-05 |

## Ampliación aprobada (2026-10-18)
| Orden | Historia | Depende de |
|---|---|---|
| 11 | HU-20 Diseño visual | MVP construido |
| 12 | HU-17 Dirección del negocio | HU-01 |
| 13 | HU-18 Tira de días del mes | HU-04 |
| 14 | HU-19 Gráfico semanal en la agenda | HU-09 |

## Planes y suscripciones (aprobado 2026-10-18)
| Orden | Historia | Depende de |
|---|---|---|
| 15 | HU-21 Catálogo de planes | ADR-0004 |
| 16 | HU-22 Prueba gratuita | HU-21 |
| 17 | HU-23 Estados de suscripción y acceso | HU-22 |
| 18 | HU-24 Límite de profesionales | HU-23 |
| 19 | HU-25 Pantalla de planes | HU-23 |
| 20 | HU-26 Avisos de vencimiento | HU-22 |
| 21 | HU-27 Interfaz de pagos | HU-25 |
| 22 | HU-28 Verificación de email | HU-22 |
| 23 | HU-29 Suscribirse con Mercado Pago | HU-27, ADR-0005 |
| 24 | HU-30 Dar de baja o cambiar de plan pagando | HU-29 |
| 25 | HU-31 Pago por transferencia | HU-27 |

## Ampliación aprobada (2026-10-28)
| Orden | Historia | Depende de |
|---|---|---|
| 26 | HU-13 Bloquear días u horarios puntuales | HU-03, HU-04 |
| 27 | HU-14 Aviso al negocio ante cada reserva o cambio | HU-05 |
| 28 | HU-32 Escribirle al cliente por WhatsApp con un toque | HU-14 |
| 29 | HU-33 Precio del servicio | HU-02 |
| 30 | HU-34 Marcar si el cliente vino | HU-09 |
| 31 | HU-35 Panel de ingresos y reportes | HU-33, HU-34 |

## Futuro
- HU-11 Recordatorio automático por WhatsApp (API paga de Meta: después de los planes pagos)
- HU-12 Pago o seña al reservar (resuelta como seña por transferencia)
- HU-15 Reservar con "cualquier profesional disponible"
- HU-16 Suscripción y cobro a los negocios (resuelta por HU-21 a HU-31)

## Pendiente del Founder
- Nada pendiente: P1, P2 y P3 del `PRD.md` están resueltas.

Alcance del MVP aprobado por el Founder el 2026-10-13.
