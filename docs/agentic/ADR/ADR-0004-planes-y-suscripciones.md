# ADR-0004: Planes, prueba gratuita y suscripciones

- Estado: aceptado (decisiones aprobadas por el Founder el 2026-10-18)
- Fecha: 2026-10-18
- Decide: Founder (reglas comerciales) y Architect (diseño técnico)

## Contexto
Para vender TurnoFacil como SaaS hace falta saber, para cada negocio, qué plan tiene, si está en prueba o pagando
y qué puede hacer. La auditoría del repo (2026-10-18) no encontró nada de planes, límites, pagos ni suscripciones:
no hay un sistema que reusar ni que duplicar. Sí hay piezas reutilizables: usuarios y negocios (uno a uno),
aislamiento por negocio en todas las vistas del panel, el sistema de emails y la tarea programada de Render.

## Decisión
Una app nueva `billing` dentro del mismo proyecto Django.

### Modelo de datos
- `Plan`: código único, nombre, precio mensual (decimal), moneda (ARS), máximo de profesionales activos,
  funcionalidades (lista de códigos del catálogo), si es público y orden. Se carga con una migración de datos y
  se edita con el comando `manage.py set_plan`, sin desplegar código. Planes: `esencial`, `profesional`,
  `negocio` (públicos) y `piloto` (sin costo, no público).
- `Subscription`: una por negocio (uno a uno). Plan actual, plan elegido, estado, inicio y fin de la prueba, fin
  del período pago, fecha de cancelación y campos opcionales del proveedor de pagos (sin datos de tarjetas).
- `SubscriptionEvent`: cada cambio de estado con estado anterior, nuevo y motivo (trazabilidad).
- `TrialNotice`: avisos de vencimiento enviados, únicos por suscripción y tipo (idempotencia en la base).

### Catálogo de funcionalidades
Códigos explícitos en `billing/catalog.py`: `booking.online` (la página pública toma reservas), `panel.edit`
(crear, editar, reprogramar y cancelar desde el panel), más funcionalidades descriptivas que existen hoy
(emails de confirmación y recordatorio, autogestión del cliente, agenda con gráfico). Los tres planes incluyen
todas; se diferencian solo por el límite de profesionales (decisión del Founder). Ver la agenda, los datos y los
planes no requiere plan: es lo que queda en solo lectura.

### Estados y transiciones
| Estado | Significa | Acceso |
|---|---|---|
| `trialing` | Prueba activa | Plan Profesional hasta el fin de la prueba |
| `trial_expired` | Prueba vencida sin plan pago | Solo lectura |
| `pending_payment` | Eligió un plan, falta confirmar el pago | Prueba si todavía está vigente; si no, solo lectura |
| `active` | Pago confirmado (o plan sin costo) | Su plan hasta el fin del período (sin fin para el piloto) |
| `past_due` | Problema con un cobro | Su plan durante una gracia de 3 días tras el fin del período; después, solo lectura |
| `canceled` | Suscripción terminada | Solo lectura |

Transiciones permitidas, todas en el servidor y registradas: `trialing` a `pending_payment`, `trial_expired`,
`active`; `trial_expired` a `pending_payment`, `active`; `pending_payment` a `active`, `trial_expired`,
`pending_payment` (cambia el plan elegido); `active` a `past_due`, `canceled`, `pending_payment` (cambio de plan);
`past_due` a `active`, `canceled`; `canceled` a `pending_payment`, `active`. Cualquier otra se rechaza.
`active` solo se alcanza con una confirmación del proveedor de pagos o con una concesión manual de un operador
(comando `grant_plan`, para el piloto).

El acceso se calcula en cada pedido a partir del estado y de las fechas, así que una prueba vencida deja de dar
acceso aunque la tarea programada todavía no haya actualizado el estado.

### Control de acceso
Una sola función, `billing.access.get_access(business)`, devuelve el estado efectivo, el plan efectivo, los
permisos y el límite. Todas las vistas del panel que modifican datos usan un decorador que la consulta; la página
pública y la reserva consultan `booking.online`. Las plantillas solo leen el mismo objeto: no hay reglas
repetidas en el frontend.

### Límites
Crear o reactivar un profesional exige estar por debajo del límite del plan efectivo. Elegir un plan exige que
los profesionales activos entren en su límite. Si un negocio queda por encima (por ejemplo, por una baja
procesada por el proveedor), no se borra nada: se avisa en el panel y solo se bloquea agregar o reactivar.

### Avisos
La tarea de Render que ya corre cada 15 minutos ejecuta también `manage.py run_billing_tasks`: actualiza
pruebas vencidas y envía el aviso más urgente que corresponda (7, 3 o 1 día antes, o finalizada), registrado en
`TrialNotice`. No se agregan dependencias.

### Pagos
`billing/payments.py` define la interfaz de proveedor (`start_checkout`, `handle_confirmation`). El proveedor por
defecto no cobra: deja la suscripción en `pending_payment` y muestra el siguiente paso. Conectar un proveedor
compatible con Argentina (por ejemplo, suscripciones de Mercado Pago) será un ADR aparte. TurnoFacil no guarda
datos de tarjetas: el cobro y los datos de pago quedan en el proveedor.

### Ampliación (2026-10-18): verificación de email
La prueba empieza cuando el dueño confirma su email (link firmado que vence a los 3 días), no al registrarse:
es el momento en que el negocio queda activo. Hasta entonces el panel muestra solo la pantalla de
confirmación y la página pública no toma reservas. Cada cuenta guarda además su email canónico (minúsculas,
sin "+etiqueta" y sin puntos en Gmail), que es único: un mismo buzón no puede abrir otra cuenta ni otra prueba.
Las cuentas existentes quedan verificadas por la migración `accounts.0002_email_verification`.

## Opciones descartadas
- Catálogo en el código: cambiar un precio exige un deploy. Se prefirió la base con un comando de edición.
- Habilitar el panel de administración de Django para editar planes: suma superficie de ataque para un uso
  esporádico; un comando alcanza por ahora.
- Diferenciar planes por funcionalidades: hoy la única diferencia real es el tamaño del equipo.

## Consecuencias
- Cada negocio nuevo empieza en prueba; los existentes reciben una prueba de 14 días desde la migración.
- La verificación de email y el email canónico frenan alias y emails inventados, pero una persona con varios
  buzones reales todavía puede abrir varias cuentas. Frenarlo del todo exigiría verificar teléfono o CUIT.
- Hasta conectar un proveedor, ningún negocio pasa a `active` salvo concesión manual.

## ¿Es reversible?
Sí. La app `billing` es aditiva; quitarla devuelve el acceso libre. Los datos de negocios no cambian.
