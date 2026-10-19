# Entrega: planes, prueba gratuita y suscripciones (Fase 11)

- Fecha: 2026-10-18
- Alcance: HU-21 a HU-27 (`USER_STORIES.md`), diseño en `ADR/ADR-0004-planes-y-suscripciones.md`.
- Estado: implementado y verificado en desarrollo. No desplegado. Sin cobros reales.

## Qué se hizo
- App `billing` dentro del mismo proyecto, reutilizando usuarios, negocios, emails y la tarea programada.
- Catálogo de planes en la base (Esencial ARS 14.900 / 1 profesional, Profesional ARS 24.900 / 5,
  Negocio ARS 39.900 / 15, y Piloto sin costo, no público), editable con `set_plan`.
- Catálogo explícito de funcionalidades (`billing/catalog.py`); los tres planes incluyen todas y se diferencian
  por el límite de profesionales activos.
- Prueba gratuita de 14 días (configurable con `TRIAL_DAYS`) que empieza al crear el negocio, sin tarjeta,
  con fechas calculadas y guardadas en el servidor; una sola por negocio.
- Seis estados de suscripción con transiciones permitidas y registradas (`SubscriptionEvent`).
- Control de acceso central (`billing/access.py`) aplicado en el servidor a todas las acciones de edición del
  panel, a la página pública de reservas y a la reprogramación por el cliente.
- Solo lectura al vencer la prueba o sin plan activo; los turnos existentes se respetan.
- Límite de profesionales al crear, al reactivar y al elegir plan; sin borrados automáticos si se excede.
- Pantalla de planes con el copy aprobado, aviso de días restantes y de solo lectura en el panel.
- Avisos por email al dueño 7, 3 y 1 día antes y al finalizar, sin duplicados.
- Interfaz de proveedor de pagos desacoplada; ninguna activación sin confirmación verificada.
- Migración de negocios existentes con política documentada (`PLANES_MIGRACION_Y_PAGOS.md`).

## Migraciones agregadas
| Migración | Efecto | Reversible |
|---|---|---|
| `billing/migrations/0001_initial.py` | Crea `Plan`, `Subscription`, `SubscriptionEvent` y `TrialNotice` con sus restricciones | Sí |
| `billing/migrations/0002_seed_plans_and_trials.py` | Carga los cuatro planes y da prueba de 14 días a los negocios sin suscripción | Sí (borra solo datos de `billing`) |

## Archivos
Nuevos:
- `billing/` (app completa): `models.py`, `catalog.py`, `services.py`, `access.py`, `decorators.py`,
  `payments.py`, `notices.py`, `views.py`, `urls.py`, `context_processors.py`, `apps.py`,
  `management/commands/` (`run_billing_tasks`, `set_plan`, `grant_plan`), `migrations/` y `tests/`.
- `templates/billing/plans.html`, `templates/billing/emails/trial_notice.txt`.
- `docs/agentic/ADR/ADR-0004-planes-y-suscripciones.md`, `docs/agentic/PLANES_MIGRACION_Y_PAGOS.md`, este archivo.

Modificados:
- `config/settings.py` (app, contexto, `TRIAL_DAYS`, `PAST_DUE_GRACE_DAYS`, `PAYMENT_PROVIDER`) y `config/urls.py`.
- `businesses/views.py` (solo lectura y límite de profesionales), `bookings/panel_views.py` (solo lectura),
  `bookings/views.py` (página pública y reprogramación según el plan).
- `templates/base.html` (pestaña Planes, avisos, mensajes), `templates/businesses/panel.html`,
  `templates/businesses/service_list.html`, `templates/businesses/professional_list.html`,
  `templates/bookings/appointment_detail.html`, `static/css/app.css`.
- `render.yaml` (la tarea programada corre también `run_billing_tasks`).
- Documentación: `PRD.md`, `USER_STORIES.md`, `ACCEPTANCE_CRITERIA.md`, `BACKLOG.md`, `DATABASE_SCHEMA.md`,
  `DEPLOYMENT.md`, `AGENTS.md`, `README.md`.

## Pruebas ejecutadas
- Suite completa: 249 tests, todos OK (65 nuevos en `billing/tests/`), contra PostgreSQL.
- Lint y formato (`ruff`): sin errores. `manage.py check` y migraciones: sin problemas.
- Cobertura de la Fase 10:

| Requisito | Tests |
|---|---|
| Alta de negocio y comienzo de la prueba | `TrialTests.test_signup_starts_a_14_day_trial_on_the_professional_plan` |
| Cálculo de los 14 días | mismo test y `test_trial_length_is_configurable`, `test_days_left_counts_partial_days` |
| No reiniciar la prueba | `test_trial_cannot_be_restarted`, `test_every_business_has_exactly_one_subscription` |
| Acceso durante la prueba | `test_trial_grants_professional_access_and_days_left` |
| Restricciones en backend al vencer | `ReadOnlyEnforcementTests` (todas las rutas de edición, GET y POST) |
| Contratación y cambio de plan sin cobro | `TransitionTests`, `PlansPageTests`, `PaymentInterfaceTests` |
| Límites de profesionales | `ProfessionalLimitTests` |
| Protección entre negocios | `IsolationTests` y los tests de aislamiento previos del panel |
| Conservación de turnos | `test_existing_appointments_are_honored`, `test_nothing_is_deleted_when_the_trial_ends` |
| Avisos sin duplicados | `TrialNoticeTests` |
| Negocios existentes tras la migración | `ExistingBusinessTests`, `MigrationReversibilityTests` |

- Verificación manual en la app local: pantalla de planes, elección de plan (pago pendiente), vencimiento
  simulado, email de prueba finalizada, panel en solo lectura, rutas de edición bloqueadas y página pública sin
  reservas.

## Pendientes para pagos reales
Detalle en `PLANES_MIGRACION_Y_PAGOS.md`, sección 2: elegir proveedor (ADR), implementar `PaymentProvider`,
webhook verificado e idempotente, mapeo de eventos a estados, credenciales en variables de entorno, pantallas de
retorno y gestión, comprobantes, tests con el sandbox del proveedor y QA gate.

## Limitaciones y riesgos abiertos
- Sin proveedor de pagos, ningún negocio pasa a `active` salvo concesión manual (`grant_plan`). Hasta conectar
  uno, el pago se coordina por fuera y un operador activa el plan.
- `grant_plan` sin `--months` activa sin vencimiento (solo para el piloto). Para un pago coordinado a mano se
  usa `--months N`, y la renovación la tiene que repetir un operador hasta integrar el proveedor.
- Sin verificación de email, se pueden obtener pruebas nuevas creando otra cuenta.
- El estado `past_due` y su gracia de 3 días solo se alcanzan con un proveedor conectado.
- No hay pantalla interna para editar planes: se usa el comando `set_plan` desde la consola de Render.
- No se desplegó a producción.
