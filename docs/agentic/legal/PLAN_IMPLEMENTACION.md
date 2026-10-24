# Plan de implementación legal: TurnoFacil

- Estado: **aprobado e implementado en la rama `feat/legal-compliance`** (2026-10-24), sin desplegar ni
  publicar documentos. Hechos: pasos 1, 2, 3, 4, 6 y 7. Pendiente: paso 5 (descargar las fuentes requiere
  permiso del Founder) y paso 8 (depende del abogado). Detalle por hallazgo: sección 7.3 de `LEGAL_REVIEW.md`.
- Diferencias con lo planeado:
  - El comando de publicación usa `--doc-version` (`--version` choca con una opción de Django).
  - Paso 4: la solicitud se aplica cuando el dueño la confirma desde el link del email, para que nadie
    dé de baja una cuenta ajena. El código se manda al instante igual. Va como consulta al abogado.
  - Paso 1: `/contacto/` y su enlace aparecen solo con `LEGAL_CONTACT_EMAIL` cargado; los datos del titular
    salen de variables `LEGAL_*` (ver `.env.example`).
  - Paso 6: los comandos son `export_business_data`, `customer_data [--erase]`, `delete_business` y
    `purge_old_data`. `purge_old_data` no está en la tarea programada hasta que se decida el plazo.
- Fecha: 2026-10-24
- Base: `LEGAL_REVIEW.md` de esta carpeta (hallazgos H01 a H22; H17 a H22 agregados el 2026-10-24 con el flujo de señas).
- Regla: se implementa en una rama, con tests, y no se despliega a producción sin autorización del Founder.
  Los documentos se publican solo cuando `OWNER_LEGAL_DATA.md` está completo y el abogado revisó el texto.

## Separación de responsabilidades
| Tipo | Qué |
|---|---|
| Cambios técnicos (Builder) | Pasos 1 a 7 (el 8 depende del abogado) |
| Decisiones comerciales (Founder) | Datos del titular, plazos de conservación, reembolsos voluntarios, implementar los botones aunque se discuta su aplicabilidad, fuentes locales, campos y registro manual de la seña |
| Validaciones jurídicas (abogado) | Sección 10 del `LEGAL_REVIEW` |

## Pasos técnicos
Respetan el stack (Django, plantillas en el servidor, sin dependencias nuevas). Cada paso es un commit chico.

### 1. Documentos legales versionados (H01, H02, H07, H12)
- App nueva `legal` con el modelo `LegalDocument`: `kind` (`terms`, `privacy`), `version`, `effective_at`,
  `body` (texto publicado), `body_sha256`, `published_at`. Una versión publicada no se edita: se crea otra
  (lo garantiza `save()` y un test). La fuente de verdad es la base, no la plantilla.
- Vistas públicas `/terminos/`, `/privacidad/` (última versión vigente, con versión y fecha visibles) y
  `/terminos/v/<version>/` para versiones anteriores. `/contacto/` con titular, canales y horario.
- Comando `publish_legal_document <kind> <archivo>`: se niega a publicar si el texto contiene `[COMPLETAR]`
  o `BORRADOR` (test).
- Pie con enlaces (Términos, Privacidad, Contacto, Baja de servicio, Arrepentimiento) en `base.html`, en la
  home y en la página de reservas.

### 2. Aceptación en el registro y registro trazable (H01, H10)
- `SignupForm`: casilla `accept_terms` (desmarcada, obligatoria) con el texto «Acepto los
  [Términos y Condiciones]» y enlace que abre en otra pestaña. Debajo, sin casilla, el aviso «Al registrarte
  tratamos tus datos según la [Política de Privacidad]»: no se pide consentimiento porque la base es la
  relación contractual (art. 5.2 d); a confirmar por el abogado.
- Modelo `LegalAcceptance`: `user` (o `business`), `document` (FK a la versión exacta), `accepted_at` (UTC,
  del servidor), `context` (`signup`, `reacceptance`), `action` (`checkbox`). Sin IP ni agente de usuario
  (no hacen falta para el fin probatorio que se busca; decisión revisable). Se crea en la misma transacción
  que la cuenta. Sin vistas públicas; consulta solo por `manage.py` (como hoy con las cuentas).
- Usuarios existentes (incluida la cuenta piloto): **no** se crea una aceptación retroactiva. Al próximo ingreso
  se muestra la pantalla de aceptación de la versión vigente; hasta aceptarla, el panel no avanza.
- Al publicar una versión nueva de los términos, se repite la re-aceptación.
- Tests: no se puede registrar sin la casilla (POST directo sin el campo); la aceptación guarda la versión
  vigente; no se crea aceptación si el registro falla; un usuario existente sin aceptación es redirigido;
  la casilla arranca desmarcada.

### 3. Aviso de privacidad en la reserva (H02, H03)
Reemplazar el aviso de `booking_page.html` por uno completo y corto: quién es responsable (el negocio, con su
nombre), que TurnoFacil gestiona el turno por su cuenta, para qué se usan los datos, que son necesarios para
reservar, y enlace a la política y a cómo ejercer derechos. **Sin casillas**: la reserva es la relación con el
negocio. Mismo texto en el formulario del panel como recordatorio al dueño. Test de que el aviso aparece.

### 4. Botón de baja y botón de arrepentimiento (H05, H06)
- Enlaces "Baja de servicio" y "Arrepentimiento" en el pie de la home, visibles sin iniciar sesión.
- Página pública `/baja/` con un formulario: email de la cuenta, tipo (baja o arrepentimiento), sin registración
  ni login. Validación en el servidor, campo trampa y límite por IP (reusar `accounts/throttle.py`).
- Al enviar: modelo `ServiceRequest` (`kind`, `email`, `code`, `created_at`, `resolved_at`, `subscription`
  si existe) y email inmediato con el **código de identificación** (la norma pide 24 h; se envía en el acto).
  La respuesta en pantalla es la misma exista o no la cuenta (no revela qué emails están registrados).
- Efecto: si la cuenta existe, la baja usa la misma lógica que el botón del panel (`billing.views.cancel`, ruta `cancel_subscription`).
  El arrepentimiento dentro de los 10 días de la contratación da de baja y marca el reembolso para que el
  operador lo devuelva en Mercado Pago (manual, con aviso por email). Constancia por email (art. 10 ter).
- Tests de punta a punta: con cuenta activa, sin cuenta, fuera del plazo de arrepentimiento, doble envío.

### 5. Fuentes locales (H04)
Descargar Bricolage Grotesque y Hanken Grotesk (OFL 1.1) a `static/fonts/` con su `OFL.txt`, declararlas con
`@font-face` y quitar Google Fonts de `base.html`. Evita que Google reciba la IP de cada visitante. Revisión
visual en móvil y escritorio antes de cerrar.

### 6. Conservación, borrado y derechos (H03, H09)
- Comando `purge_old_data`: borra (o anonimiza) turnos pasados más antiguos que el plazo decidido por el
  Founder y cuentas cerradas después de su plazo. Corre con la tarea programada. Tests con fechas límite.
- Comando para operadores `export_business_data <slug>` y `delete_business <slug>` para responder pedidos de
  acceso y supresión dentro de los plazos (10 días corridos y 5 días hábiles).
- Procedimiento de respuesta en `docs/agentic/legal/PROCEDIMIENTO_DERECHOS.md` (quién recibe, cómo se
  verifica la identidad sin pedir de más, cómo se responde sin exponer datos de otros, plazos).

### 7. Seña (H11, H17, H20, H21, H22)
Hecho confirmado por el Founder y verificado en el código (2026-10-24): la seña es una transferencia directa
del cliente al negocio, fuera de TurnoFacil. **Restricciones de este paso:** no se integra una pasarela de
pagos, no se cambia el flujo de reserva (el turno sigue confirmándose igual), no se agrega verificación de
transferencias y no se tocan datos reales. Solo cambian textos y se agregan campos que carga el negocio.

Cambios de interfaz propuestos (sin implementar):
- **I1. Texto corregido** en `_deposit.html` y `emails/confirmation.txt`: "La seña la recibe directamente
  {negocio}. TurnoFacil no recibe el dinero ni verifica el pago." (H20)
- **I2. Antes de confirmar**, en el resumen del turno (`booking_page.html`), en un bloque visible y no en
  letra chica: monto, titular de la cuenta, cómo se confirma el pago y las condiciones del negocio. Alias y
  CBU pueden seguir mostrándose después de confirmar. (H17)
- **I3. Campo nuevo `conditions`** en `DepositSettings` ("Condiciones de la seña: qué pasa si cancelás,
  reprogramás o no transferís"), **opcional** (decisión del Founder, 2026-10-24). Se muestra en I2, en el
  detalle del turno y en el email. Ayuda debajo del campo para el dueño: conviene cargarlas, porque sin ellas
  el cliente no sabe qué pasa con su seña; deben respetar los derechos del cliente; TurnoFacil no las redacta
  ni las aprueba. Si el campo está vacío, el cliente ve un texto neutro: "{negocio} no cargó condiciones para
  la seña. Consultalas antes de transferir." No se inventan condiciones por el negocio. Migración reversible
  con test. (H17)
- **I4. Cancelación:** en `cancel_confirm.html` y en `emails/cancelled.txt`, si había seña: "Si pagaste
  una seña, su devolución depende de {negocio}: {condiciones o el texto neutro}." (H22)
- **I5. Pantalla del dueño** (`deposit_settings.html`): recordar que confirma la recepción con su cliente y
  gestiona las devoluciones, y que sus datos de cuenta los ve cada cliente que reserva. (H21)

- **I6. "Seña recibida" manual** (aprobado por el Founder, 2026-10-24). Campo `deposit_received_at` en
  `Appointment` (vacío = sin marcar), con un botón en el turno del panel para marcarlo y desmarcarlo. Solo lo
  cambia el dueño de ese negocio (test de aislamiento). En la agenda, los turnos con seña pedida muestran
  "Seña pendiente" o "Seña recibida". El texto aclara que lo marca el negocio y que TurnoFacil no verifica
  ninguna transferencia. No cambia el estado del turno ni dispara cancelaciones. Al cliente se le muestra
  "{negocio} registró que recibió tu seña" cuando está marcado; nunca "pago verificado".
- **I7. Texto para el cliente sobre la confirmación** (opción B, confirmada por el Founder el 2026-10-24):
  "Tu turno está confirmado. Si {negocio} no recibe la seña, puede cancelarlo según sus condiciones."

Tests: los existentes de `businesses/tests/test_deposit.py` siguen en verde; nuevos para `conditions`
vacío y cargado, para que I2 aparezca antes de confirmar, para I4 en la cancelación y para I6 (marcar,
desmarcar, otro negocio no puede, el estado del turno no cambia).

#### Turno confirmado aunque no se transfiera: decidido
Decisión del Founder (2026-10-24): **opción B**. Se conserva el análisis:
```
FOUNDER DECISION (resuelta: B)

- Decisión: qué pasa con un turno cuya seña no se transfiere.
- Opciones:
  A. Dejarlo como hoy (confirmado igual), sin marca ni aviso.
  B. Confirmado igual + marca manual "seña recibida" (I6) + aviso claro al cliente (I7). Si no llega la seña,
     el dueño cancela el turno desde el panel, como ya puede hacerlo hoy, según las condiciones que informó.
  C. Estado nuevo "pendiente de seña": reserva el horario por un plazo, se confirma cuando el dueño marca la
     seña y se libera solo si vence el plazo.
- Recomendación: B.
- Impacto: B es chico y no cambia el flujo de reserva (solo I6 e I7, ya planificados). C toca la restricción
  de no superposición, la disponibilidad, los recordatorios, los emails y una tarea programada nueva.
- Riesgo: con B, el dueño tiene que acordarse de cancelar los turnos sin seña. Con C, si el dueño se olvida
  de marcar una seña que sí se pagó, el sistema cancela solo a alguien que pagó: es un reclamo seguro contra
  el negocio y, posiblemente, contra TurnoFacil. C se puede reconsiderar si hay negocios con muchas
  ausencias de clientes que no pagan la seña.
```

### 8. Botón de arrepentimiento en las reservas (H18)
Solo si el abogado concluye que corresponde. Se diseñaría como una opción del negocio en su página de reservas;
no se planifica hasta tener esa respuesta.

## Verificación (fase 6)
- `ruff check .`, `ruff format --check .`, `manage.py check`, `manage.py test` en verde.
- Pruebas manuales en el navegador: enlaces legales desde home, panel y reserva; registro con y sin casilla;
  teclado y móvil; flujo de baja y arrepentimiento completo con el email en consola; cookies reales en las
  herramientas del navegador (solo `sessionid` y `csrftoken`; ninguna petición a Google).
- Completar `LEGAL_LAUNCH_CHECKLIST.md` (plantilla de NEXORA) con la evidencia y actualizar el estado de
  los hallazgos en `LEGAL_REVIEW.md`.

## Condiciones antes de publicar los documentos
1. `OWNER_LEGAL_DATA.md` sin `[COMPLETAR]` obligatorios.
2. Abogado consultado sobre los asuntos de alta urgencia de la sección 10.
3. DPA de proveedores guardados o mecanismo de transferencia definido (H04).
4. Pasos 1 a 4 y 6 implementados y probados; los textos describen lo que el sistema hace.
5. Autorización del Founder para desplegar.
