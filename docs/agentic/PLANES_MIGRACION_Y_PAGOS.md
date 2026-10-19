# Planes: migración de negocios existentes y preparación para pagos

- Fecha: 2026-10-18
- Base: `ADR/ADR-0004-planes-y-suscripciones.md`, decisiones del Founder del 2026-10-18.

## 1. Negocios existentes (Fase 9)

### Inventario al 2026-10-18
| Entorno | Negocios | Estado operativo | Plan y estado asignados |
|---|---|---|---|
| Producción (Render) | Ninguno: TurnoFacil todavía no se desplegó | No aplica | No aplica |
| Desarrollo local | ValenBarber (creado el 2026-10-13) | Con datos de prueba del Founder | Prueba de 14 días desde la migración (`trialing`, plan Profesional) |
| Producción, después del deploy | Estética piloto (a crear) | Piloto comercial | Plan `piloto`, sin costo y sin vencimiento, activado con `grant_plan` |

### Política de migración
1. La migración `billing.0002_seed_plans_and_trials` crea el catálogo y le da a **cada negocio que no tenga
   suscripción** una prueba de 14 días que empieza en el momento de migrar. Es la política aprobada por el Founder
   para negocios existentes.
2. No borra ni modifica turnos, profesionales, servicios ni datos de clientes. Solo agrega filas en las tablas de
   `billing`. Lo cubren los tests de `billing/tests/test_migration.py`.
3. Correrla dos veces no cambia nada: solo actúa sobre negocios sin suscripción.
4. Excepción comercial del piloto: la estética piloto recibe el plan `piloto` con
   `python manage.py grant_plan <slug> piloto`, ejecutado por un operador después del deploy (paso incluido en
   `DEPLOYMENT.md`). Queda registrado en el historial de la suscripción.
5. Reversibilidad: las dos migraciones de `billing` se revierten con `python manage.py migrate billing zero`, que
   borra solo las tablas de planes y suscripciones; los negocios y sus datos quedan intactos (probado en
   `MigrationReversibilityTests`). Revertir devuelve el acceso libre, como antes de los planes.
6. En producción, antes de cualquier migración futura que cambie estados de suscripción, se exporta la base
   (`DEPLOYMENT.md`, Rollback) y se documenta el efecto esperado por negocio.

### Reactivaciones y nuevas pruebas
- Una sola prueba por negocio, que empieza al crearlo. No hay forma, desde la app, de reiniciarla ni extenderla.
- Un negocio con la prueba vencida o la suscripción cancelada puede volver a elegir un plan; no recibe otra prueba.
- Regalar días o una prueba nueva es una decisión comercial manual (operador), no una función de la app.
- Desde HU-28 la prueba empieza al confirmar el email y un mismo buzón (incluidos sus alias) no puede abrir otra
  cuenta. Limitación que queda: alguien con varios buzones reales puede abrir varias cuentas; frenarlo del todo
  exigiría verificar teléfono o CUIT.

## 2. Preparación para pagos (Fase 8)

### Lo que ya está
- La lógica de planes, permisos y estados (`billing/services.py`, `billing/access.py`) no depende de ningún
  proveedor.
- `billing/payments.py` define la interfaz `PaymentProvider` con dos operaciones:
  - `start_checkout(subscription, plan)`: inicia el pago en el proveedor; no puede marcar nada como pago.
  - `verify_confirmation(payload)`: verifica una notificación del proveedor y devuelve su referencia y el fin del
    período pago.
- `confirm_payment(provider, payload)` es el único camino del código que activa una suscripción por pago, y solo
  después de que el proveedor verificó la notificación.
- El proveedor configurado es `ManualProvider` (variable `PAYMENT_PROVIDER`): registra la elección como
  `pending_payment` y avisa que el pago se coordina por fuera. No simula pagos ni cobra.
- Mientras tanto, cuando un pago se cobra por fuera de la app, un operador activa el plan con
  `grant_plan <slug> <plan> --months N` (queda registrado y vence al terminar los meses pagos).
- La base guarda solo la referencia de la suscripción en el proveedor (`provider`, `provider_subscription_id`).
  No hay campos para números de tarjeta, CVV, credenciales ni otros datos de medios de pago.

### Componentes necesarios para cobrar de verdad (fase posterior, con su propio ADR)
1. **Elección del proveedor** compatible con Argentina y con cobro recurrente. Propuesta: suscripciones de
   Mercado Pago con acreditación a 35 días (`ADR/ADR-0005-proveedor-de-pagos.md`). Usar su checkout oficial y sus tokens: los datos de la tarjeta nunca pasan por TurnoFacil.
2. **Implementación de `PaymentProvider`** para ese proveedor: crear la suscripción o preferencia de pago y
   devolver la URL de su checkout.
3. **Endpoint de notificaciones (webhook)** público, con verificación de firma o consulta al proveedor antes de
   creer cualquier aviso, protección contra repeticiones (guardar los identificadores de eventos procesados) y
   respuesta idempotente.
4. **Mapeo de eventos a estados**: pago aprobado a `active` (con fin de período), pago rechazado o vencido a
   `past_due`, baja a `canceled`. Todo por medio de `billing/services.py`.
5. **Credenciales del proveedor** solo en variables de entorno de Render, nunca en el repo.
6. **Pantallas**: volver del checkout (éxito, pendiente, error) y gestionar o dar de baja la suscripción.
7. **Comprobantes y facturación** según la normativa argentina: definir si los emite el proveedor o otro servicio.
8. **Tests** con notificaciones de prueba del proveedor y verificación en su entorno de pruebas (sandbox).
9. **Revisión de seguridad** del webhook y del flujo antes de habilitarlo (QA gate).
