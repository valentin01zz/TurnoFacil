# Arquitectura: TurnoFacil

- Estado: aprobado por el Founder (2026-10-13)
- Fecha: 2026-10-13
- Base: `PRD.md`, `ACCEPTANCE_CRITERIA.md`, `ADR/ADR-0001-stack-de-la-aplicacion.md`

## 1. Visión general
Una sola aplicación Django que atiende tres cosas: la página pública de reservas, el panel del negocio y una
tarea programada de recordatorios. Una base PostgreSQL. Sin colas, sin caché, sin frontend separado.

```
Cliente final ──► /b/<slug>/  (reservar)        ┐
Cliente final ──► /t/<token>/ (gestionar turno) ├─► Django ──► PostgreSQL
Dueño ─────────► /panel/      (con sesión)      ┘      │
Tarea programada ─► send_reminders (cada 15 min) ──────┴──► Email (SMTP/API)
```

## 2. Estructura del repo
```
manage.py
config/            settings, urls, wsgi
accounts/          usuario (login por email), registro, sesión
businesses/        negocio, servicios, profesionales, horarios de atención
bookings/          turnos, disponibilidad, emails, recordatorios
templates/         plantillas HTML
static/            una hoja de estilos propia (mobile-first), JS mínimo
requirements.txt   dependencias de ejecución
requirements-dev.txt
.env.example
```
Tests dentro de cada app (`tests/`).

## 3. Dependencias
- Ejecución: `Django` 5.2 LTS, `psycopg` (driver de PostgreSQL).
- Desarrollo: `ruff` (lint y formato).
- Tests: el runner de Django, sin librerías extra.
- Sin typecheck en el MVP: no se agrega `mypy` hasta que haga falta.
- Servidor de producción y archivos estáticos: se definen en el ADR de hosting.

## 4. Multi-negocio y autorización
- Base compartida: cada servicio, profesional y turno pertenece a un negocio (`business_id`).
- Un usuario es dueño de exactamente un negocio (S4). Los profesionales no tienen usuario (S5).
- Toda vista del panel exige sesión y filtra siempre por el negocio del usuario. Un id de otro negocio
  responde 404. Esto se implementa una sola vez en un mixin común y se testea por cada vista.
- La parte pública identifica al negocio por `slug` y al turno por un token aleatorio imposible de adivinar.

## 5. Autenticación
- Modelo de usuario propio con email como identificador, definido desde la primera migración (cambiarlo
  después es costoso).
- Contraseñas y sesiones con el sistema de Django. Protección CSRF activa en todos los formularios.
- Recuperación de contraseña con las vistas incluidas en Django. No está en los criterios de aceptación, pero
  sin ella un dueño que olvida la contraseña pierde el acceso; el costo es mínimo.

## 6. Disponibilidad y superposición de turnos
- Los horarios libres se calculan en el momento: horario de atención del profesional para ese día, menos los
  turnos confirmados, en pasos de 30 minutos, dejando solo los inicios donde entra la duración del servicio.
  El paso es un valor de configuración (`SLOT_STEP_MINUTES`), porque puede cambiar más adelante.
- Se ofrecen fechas desde hoy hasta 60 días adelante.
- La garantía de no superposición está en la base: una restricción de exclusión de PostgreSQL sobre
  (profesional, rango horario) para turnos confirmados. Si dos reservas compiten, la base rechaza la segunda y
  la app muestra "ese horario se acaba de ocupar". No depende de que el código verifique antes.
- Al reprogramar se actualiza el mismo turno en una transacción: el horario viejo se libera al confirmar el nuevo.

## 7. Fechas y horas
Se guarda todo en UTC y se muestra en la zona horaria de Argentina (S6), configurada a nivel de aplicación.
Si aparece un negocio en otra zona, se agrega el campo al negocio.

## 8. Emails
- Tres emails al cliente: confirmación, cambio (reprogramación o cancelación desde el panel) y recordatorio.
  Todos incluyen el link de gestión.
- Se envían durante la petición, sin cola. Si el envío falla, el turno igual queda creado y el error se registra.
- En desarrollo los emails se imprimen en la consola; el proveedor real se elige en su ADR.

## 9. Recordatorios
- Cada turno guarda `reminder_due_at` (inicio menos 24 horas). Queda vacío si al reservar o reprogramar faltan
  menos de 24 horas.
- El comando `send_reminders` corre cada 15 minutos: toma turnos confirmados, futuros, con `reminder_due_at`
  vencido y sin `reminder_sent_at`; envía y marca. La marca evita duplicados aunque el comando corra dos veces.
- Reprogramar recalcula `reminder_due_at` y limpia `reminder_sent_at`.

## 10. Seguridad y datos personales
- Secretos y configuración solo por variables de entorno (`SECRET_KEY`, base de datos, email). `.env` fuera del repo.
- Validación en el backend con formularios de Django, también para datos que el frontend ya validó.
- Reservas falsas (R2): campo trampa oculto en el formulario público. Límites por IP o verificación del email
  quedan para cuando haya abuso real.
- Datos personales (R3): se guarda solo nombre, teléfono y email del cliente, y el formulario muestra un aviso
  de para qué se usan. La revisión legal queda a cargo del Founder antes de comercializar.

## 11. Decisiones de diseño validadas con el Founder (2026-10-13)
- Paso de 30 minutos entre horarios ofrecidos (el Founder cambió la propuesta inicial de 15; puede revisarse).
- Ventana de reserva de 60 días.
- Recuperación de contraseña incluida.
- El panel reprograma y cancela sin el límite de 2 horas.
- Email opcional en turnos cargados a mano.
- Sin typecheck en el MVP.

## 12. Pendiente (no bloquea al Builder)
- ADR de hosting y ADR de proveedor de email, antes del primer deploy.
