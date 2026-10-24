# Legal Review: TurnoFacil (producción, auditoría completa)

> Informe de análisis jurídico preventivo y compliance hecho por el Legal & Compliance Agent de NEXORA.
> **No constituye asesoramiento legal profesional** ni certifica que el producto esté libre de riesgos. Su
> validez se limita al alcance y la fecha indicados.

## 1. Identificación
- Producto y versión: TurnoFacil en producción (https://turnofacil.online).
- Repositorio / commit revisado: `valentin01zz/TurnoFacil`, rama `main`, commit `33cce4f`.
- Fecha de la revisión: 2026-10-24.
- Gate: Post-lanzamiento (el producto ya está en producción sin revisión legal previa).
- Profundidad: Estándar (datos personales comunes, cobros, usuarios finales; sin datos sensibles a la vista).
- Jurisdicción inicial: Argentina.
- Otras jurisdicciones posibles: EE. UU. (hosting Render en Virginia; Cloudflare; Google Fonts) y Brasil
  (Resend, región São Paulo) como países de proveedores. No hay indicios de usuarios fuera de Argentina.

## 2. Alcance y exclusiones
- Incluido: código del repo (modelos, formularios, plantillas, JS, settings, `render.yaml`), documentación en
  `docs/agentic/`, dependencias de `requirements.txt`, normativa argentina de datos, consumo y contratación a distancia.
- Excluido:
  - Inspección del sitio en producción con navegador (cookies reales, cabeceras): se infirió del código.
  - Lectura de los términos y acuerdos de tratamiento de datos (DPA) de Render, Resend, Cloudflare, Google y
    Mercado Pago: no se comprobó que existan ni qué dicen.
  - Búsqueda de marca en el INPI.
  - Obligaciones tributarias y societarias (contador).
  - Si el DNU 70/2023 modificó artículos de la Ley 24.240 citados aquí.

## 3. Hechos verificados
| Hecho | Evidencia |
|---|---|
| Datos del dueño del negocio: email, contraseña (hash de Django), nombre del negocio; email verificado; fecha de alta | `accounts/models.py`, `accounts/forms.py` (SignupForm) |
| Datos de los clientes del negocio: nombre y apellido, teléfono, email; turnos con servicio, profesional, horario | `bookings/models.py` (Appointment), `bookings/forms.py` (BookingForm) |
| El dueño también carga turnos a mano con email opcional | `bookings/forms.py` (PanelAppointmentForm) |
| IP y email canónico guardados para límites de intentos, borrados a las 24 h | `accounts/throttle.py` (`KEEP = 1 día`) |
| No se guardan datos de tarjeta; solo la referencia de la suscripción en Mercado Pago y el email del pagador | `billing/models.py` (Subscription, CheckoutAttempt) |
| Cobro mensual con renovación automática por Mercado Pago; prueba gratis de 14 días sin tarjeta | `templates/billing/plans.html`, `config/settings.py` (`TRIAL_DAYS`) |
| Baja de la suscripción existe, pero solo dentro del panel (requiere iniciar sesión) | `templates/billing/cancel_confirm.html`, `billing/urls.py` |
| Seña por transferencia: TurnoFacil muestra los datos bancarios del negocio; no cobra ni intermedia | `businesses/deposit.py`, `templates/bookings/_deposit.html` |
| **Confirmado por el Founder (2026-10-24) y verificado en el código:** la seña es una transferencia directa del cliente al negocio, por fuera de TurnoFacil. TurnoFacil no la procesa, no la recibe, no la custodia ni la verifica. No hay pasarela, API de pagos, carga de comprobantes ni estado "seña pagada" en reservas o negocios; Mercado Pago solo está en `billing` y solo para la suscripción del negocio | `DepositSettings` (docstring), `grep` de `mercadopago`, `FileField`, `urllib` en `bookings` y `businesses`: sin resultados |
| Lo que se guarda de la seña son datos del negocio, no del cliente: monto fijo en ARS, titular, alias, CBU/CVU, CUIT/CUIL (opcional) e indicaciones (texto libre de hasta 300 caracteres) | `businesses/models.py` (DepositSettings) |
| El turno queda confirmado aunque no se transfiera la seña; el dueño lo sabe por la pantalla de configuración, el cliente no | `templates/businesses/deposit_settings.html` |
| Antes de confirmar, el cliente ve solo el monto (texto chico en el resumen del turno). Titular, alias o CBU e indicaciones aparecen después de confirmar: en el detalle del turno y en el email de confirmación | `booking_page.html:135`, `appointment_detail.html:36`, `emails/confirmation.txt` |
| No hay campos para condiciones de cancelación o devolución de la seña, ni para cómo se confirma la recepción. La pantalla de cancelación y el email de cancelación no mencionan la seña | `DepositSettings`, `cancel_confirm.html`, `emails/cancelled.txt` |
| Los textos al cliente dicen "TurnoFacil no verifica automáticamente el pago"; la pantalla del dueño dice "no recibe ni verifica" | `_deposit.html:11`, `confirmation.txt`, `deposit_settings.html` |
| El cliente puede cancelar o reprogramar sin costo en TurnoFacil hasta 2 horas antes; el dueño puede cancelar en cualquier momento desde el panel | `bookings/models.py` (`customer_can_change`), `templates/bookings/appointment_detail.html` |
| No hay términos, política de privacidad, cookies ni pie con enlaces legales | `templates/` (no existen), `templates/home.html` (pie sin enlaces) |
| El registro del negocio no pide aceptar términos | `templates/accounts/signup.html` |
| El formulario de reserva solo dice "Usamos tus datos solo para gestionar este turno y avisarte por email" | `templates/bookings/booking_page.html:108` |
| No se identifica en el sitio al titular del servicio ni un canal de contacto o reclamos | `templates/` |
| Cookies: solo las de Django (`sessionid`, `csrftoken`), seguras en producción. No hay analítica, píxeles ni widgets. JS sin `localStorage` | `config/settings.py`, `static/js/app.js` |
| Tercero que recibe la IP de cada visitante: Google Fonts | `templates/base.html:7-9` |
| Hosting en Render, región Virginia (EE. UU.); email por Resend, dominio en región São Paulo | `render.yaml`, `docs/agentic/DEPLOYMENT.md` |
| Los logs registran IDs, no emails ni nombres | `grep logger` en `accounts`, `billing`, `bookings` |
| No hay borrado de cuentas ni de turnos ni plazos de conservación | Sin código de supresión fuera de `throttle.py` |
| Cuenta piloto activa (plan `piloto`, sin cobro) | Memoria del proyecto, `billing/management/commands/grant_plan.py` |

## 4. Supuestos pendientes de confirmar
| Supuesto | Quién lo confirma | Impacto si es falso |
|---|---|---|
| El titular del servicio es el Founder como persona humana (no hay sociedad) | Founder | Cambia quién figura en términos y privacidad |
| La base de datos no está inscripta ante la AAIP | Founder | H08 se cierra |
| No hay contratos firmados ni DPA aceptados con Render, Resend o Cloudflare | Founder | H04 baja de nivel si existen y cubren lo exigido |
| Hay clientes pagos además del piloto, o los habrá antes de corregir | Founder | Urgencia de H01, H02, H05 |
| Los negocios no cargan datos sensibles (por ejemplo, de salud en kinesiología) en nombres de servicios | Founder / revisión de datos reales | Si los cargan, la profundidad pasa a Profunda |

## 5. Fuentes consultadas y obligaciones
Fecha de consulta de todas: 2026-10-24. Resumen y enlaces: `docs/guia-legal-saas.md` del repo NEXORA.

| Norma | Artículos | Requisito identificado | Afecta a | Evidencia | Certeza | ¿Abogado? |
|---|---|---|---|---|---|---|
| [Ley 25.326](https://servicios.infoleg.gob.ar/infolegInternet/anexos/60000-64999/64790/texact.htm) | 6 | Informar finalidad, destinatarios, responsable y domicilio, obligatoriedad y derechos al recoger datos | Registro y reserva | Aviso de una línea; sin responsable ni derechos | Alta | No |
| Ley 25.326 | 5.2 d | Sin consentimiento cuando los datos derivan de una relación contractual y son necesarios | Base jurídica de turnos y cuentas | Datos mínimos para el servicio | Alta (lectura) / interpretación | Sí |
| Ley 25.326 | 25 | El encargado no usa los datos para otros fines, no los cede, y los destruye al terminar (o guarda hasta 2 años con autorización) | Datos de clientes de los negocios | No hay cláusula de encargo ni borrado | Alta | Sí (rol) |
| Ley 25.326 | 12; [AAIP](https://www.argentina.gob.ar/transferencias-internacionales) | Prohibida la transferencia a países sin protección adecuada salvo mecanismo; EE. UU. y Brasil no están en la lista | Render, Resend, Cloudflare, Google Fonts | Sin evidencia de cláusulas | Alta | Sí |
| Ley 25.326 | 14, 16 | Acceso en 10 días corridos; rectificación o supresión en 5 días hábiles | Procedimiento de derechos | No existe | Alta | No |
| Ley 25.326 | 21, 24 | Inscripción de bases | Base de TurnoFacil | Sin inscripción (supuesto) | Alta (texto) / Media (alcance) | Sí |
| Ley 25.326 | 9 | Medidas de seguridad técnicas y organizativas | Toda la app | HTTPS, CSRF, hashes, rate limits, aislamiento por negocio | Alta | No |
| [Ley 24.240](https://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/638/texact.htm) | 1 | Consumidor = destinatario final | Calificación de los negocios | Clientes son negocios | Alta (texto) / interpretación | **Sí** |
| Ley 24.240 | 4, 38 | Información cierta y gratuita; publicar en la web el modelo del contrato de adhesión | Términos | No hay términos | Alta | No |
| Ley 24.240 | 10 ter, 10 quáter | Baja por el mismo medio, constancia en 72 h, sin cobro por baja | Baja de suscripción | Baja en el panel, sin constancia por email verificada | Alta | Sí (aplicabilidad) |
| Ley 24.240 | 34, 37 | Revocación 10 días corridos; cláusulas abusivas no convenidas | Términos y reembolsos | No hay términos | Alta | Sí (aplicabilidad) |
| [Disposición 954/2025](https://www.argentina.gob.ar/normativa/nacional/norma-417152/texto) | 1, 3, 4, 5, 6 | Botón de Arrepentimiento y Botón de Baja de Servicio visibles en el primer acceso y sin registración; código en 24 h; canal de reclamos visible; excepción 3 c para lo incorporado a la prestación de servicios a terceros | Home, baja, contacto | No hay botones públicos ni canal | Alta | **Sí** |
| [CCyC](https://servicios.infoleg.gob.ar/infolegInternet/anexos/235000-239999/235975/norma.htm) | 1105 a 1116, 1117 a 1122 | Contrato electrónico: confirmar recepción de la aceptación; revocación; cláusulas abusivas | Registro y términos | Hay email de verificación al registrarse (no confirma aceptación de términos) | Media | Sí |

Fuentes agregadas por el flujo de señas (consulta 2026-10-24):

| Norma | Artículos | Requisito identificado | Afecta a | Evidencia | Certeza | ¿Abogado? |
|---|---|---|---|---|---|---|
| [CCyC](https://servicios.infoleg.gob.ar/infolegInternet/anexos/235000-239999/235975/norma.htm) | 1059, 1060 | La seña se interpreta como confirmatoria salvo pacto de arrepentimiento; si se pacta, quien la entregó la pierde y quien la recibió la devuelve doblada | Condiciones de seña del negocio | No hay campo de condiciones | Media (texto original) | Sí |
| CCyC | 1073 a 1075 | Contratos conexos: suscripción del negocio y reserva del cliente podrían considerarse vinculados por una finalidad común | Responsabilidad de TurnoFacil frente al cliente final | — | Media | Sí |
| [Ley 24.240](https://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/638/texact.htm) | 4, 7, 8, 19 | Información previa cierta y detallada; la oferta y lo publicitado obligan; el prestador respeta las condiciones ofrecidas | Relación negocio y cliente (el negocio es el proveedor) | Información de la seña incompleta antes de reservar | Alta | No |
| Ley 24.240 | 40 | Responsabilidad solidaria por daño derivado del vicio o riesgo del servicio de productor, distribuidor, proveedor, vendedor y quien puso su marca | Riesgo de que TurnoFacil sea alcanzado frente al cliente final | — | Alta (texto) / interpretación | Sí |
| [Disposición 954/2025](https://www.argentina.gob.ar/normativa/nacional/norma-417152/texto) | 1, 3 b | El proveedor que vende servicios a distancia por la web muestra el Botón de Arrepentimiento; excepción si el servicio ya se usó | Reserva online del cliente al negocio | La página de reservas no tiene botón; sí permite cancelar gratis hasta 2 h antes | Alta (texto) / aplicación | **Sí** |
| Régimen BCRA de proveedores de servicios de pago (Com. "A" 6859 y siguientes) | — | Alcanza a quien ofrece cuentas de pago o cumple funciones en un esquema de pagos minoristas | TurnoFacil y las señas | TurnoFacil no recibe ni mueve fondos de señas | Baja (solo fuentes secundarias, por ejemplo [abogados.com.ar](https://abogados.com.ar/el-bcra-reglamento-mediante-la-comunicacion-a-6859-la-actuacion-de-los-proveedores-de-servicios-de-pago-psp/25113)); verificar en bcra.gob.ar | Baja urgencia |

Fuentes que no se pudieron verificar: impacto del DNU 70/2023 en la Ley 24.240; texto de las cláusulas modelo
(Disp. 60-E/2016 y Res. 198/2023); Ley 11.723 y 22.362 (no leídas en esta revisión); régimen de facturación.

## 6. Revisión por área
- [x] A. Propiedad intelectual (licencias de dependencias, fuentes, íconos; marca sin búsqueda en INPI)
- [x] B. Privacidad y datos
- [x] C. Contratos y obligaciones comerciales
- [x] D. Proveedores y plataformas (solo identificación; sus términos no se leyeron)
- [x] E. Jurisdicción y normativa

## 7. Hallazgos
| ID | Área | Nivel | Hallazgo | Evidencia | Fuente | Impacto posible | Base de la evaluación | Acción recomendada | Responsable | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| H01 | C | ALTO | No hay términos y condiciones ni aceptación al registrarse, y el producto ya cobra con renovación automática | Sección 3 | Ley 24.240 arts. 4 y 38; CCyC 1105 a 1108 | Reglas de cobro, baja y responsabilidad sin respaldo contractual; reclamos ante Defensa del Consumidor | Obligación de informar y publicar el modelo si hay relación de consumo; aun sin ella, sin contrato no hay reglas oponibles | Publicar términos (borrador en `TERMINOS_BORRADOR.md`) y casilla de aceptación con registro | Founder (datos), Builder (código), abogado (texto final) | ABIERTO |
| H02 | B | ALTO | No hay política de privacidad y los avisos de los formularios no cumplen el deber de información | `booking_page.html:108`, `signup.html` | Ley 25.326 art. 6 | Tratamiento sin información exigida; sanción de la AAIP | Texto del art. 6 frente al aviso actual | Publicar política (borrador en `PRIVACIDAD_BORRADOR.md`) y avisos por formulario | Founder, Builder | ABIERTO |
| H03 | B | ALTO | Rol sobre los datos de los clientes de cada negocio sin definir: TurnoFacil actúa como encargado y no hay condiciones de encargo ni borrado al terminar | `bookings/models.py`; sin supresión | Ley 25.326 art. 25 | Uso de datos sin base contractual; incumplimiento del deber de destrucción | El negocio decide para qué se usan los datos; TurnoFacil los procesa por cuenta del negocio | Cláusula de tratamiento por cuenta del negocio en los términos; borrado al cerrar cuenta y plazos | Abogado (rol), Builder | ABIERTO |
| H04 | D | ALTO | Transferencias internacionales a EE. UU. y Brasil sin mecanismo verificado | `render.yaml` (virginia), `DEPLOYMENT.md` (Resend São Paulo), `base.html` (Google Fonts) | Ley 25.326 art. 12; Disp. 60-E/2016; Res. 198/2023 | Transferencia prohibida sin garantía | Ni EE. UU. ni Brasil están en la lista de la AAIP | Revisar y guardar los DPA de Render, Resend y Cloudflare; evaluar cláusulas modelo; quitar Google Fonts sirviendo las fuentes localmente | Founder (contratos), abogado, Builder (fuentes) | DERIVADO (abogado) |
| H05 | C | INDETERMINADO | Botón de Baja de Servicio: la baja existe solo con sesión iniciada; la norma exige botón visible en el primer acceso sin registración, si el negocio es consumidor | `cancel_confirm.html` | Disp. 954/2025 arts. 4 y 5; Ley 24.240 arts. 1 y 10 ter | Sanción si los negocios se consideran consumidores | Los clientes son negocios, pero muchos son monotributistas; la excepción del art. 3 c se refiere al arrepentimiento (art. 1), no a la baja | Implementarlo igual (costo bajo): formulario público con email de la cuenta, código en 24 h y efecto real | Abogado (aplicabilidad), Founder (decisión), Builder | ABIERTO |
| H06 | C | INDETERMINADO | Botón de Arrepentimiento: no existe | `home.html` | Disp. 954/2025 arts. 1 y 3 c; Ley 24.240 art. 34; CCyC 1110 | Ídem H05 | El servicio se incorpora a la prestación de servicios a terceros (art. 3 c), lo que sugiere excepción; no hay certeza | Implementar junto con H05 (mismo formulario, otra opción) y reembolsar dentro de los 10 días de la contratación | Abogado, Founder, Builder | ABIERTO |
| H07 | C | MEDIO | No hay titular identificado ni canal visible de consultas y reclamos | `templates/` | Disp. 954/2025 art. 6; Ley 25.326 art. 6 b | Incumplimiento de información; imposibilidad de ejercer derechos | Texto de las normas | Completar `OWNER_LEGAL_DATA.md`; página de contacto y pie | Founder | ABIERTO |
| H08 | B | MEDIO | Base de datos posiblemente no inscripta ante la AAIP | Supuesto | Ley 25.326 arts. 21 y 24 | Infracción | Alcance del art. 21 discutido en la doctrina; el art. 24 alcanza bases privadas no personales | Confirmar con abogado e inscribir la base de cuentas (y, si corresponde, la de turnos como encargado) | Founder, abogado | ABIERTO |
| H09 | B | MEDIO | Sin plazos de conservación, sin borrado de cuentas ni turnos y sin procedimiento para derechos del titular | Sin código | Ley 25.326 arts. 4, 14, 16 | Datos conservados sin necesidad; no poder responder en plazo | Texto de la ley | Definir plazos (decisión del Founder), comando de borrado, procedimiento en `PLAN_IMPLEMENTACION.md` | Founder, Builder | ABIERTO |
| H10 | C | MEDIO | No hay registro trazable de aceptaciones ni versionado de documentos | Sin modelo | CCyC 1108 (confirmación de la aceptación); buena práctica probatoria | No poder probar qué texto aceptó cada negocio | Necesidad probatoria | Modelo `LegalDocument` + `LegalAcceptance` (plan) | Builder | ABIERTO |
| H11 | C | MEDIO | Revisado 2026-10-24 con el flujo confirmado. Lo que sigue abierto: los términos y la política todavía no describen que la seña es una transferencia directa al negocio y que TurnoFacil no la recibe ni la verifica (el borrador ya lo hace, pero no está publicado) | Sección 3; `TERMINOS_BORRADOR.md` sección 7 | Ley 24.240 art. 4 | Reclamos de clientes finales contra TurnoFacil por señas | Hecho verificado del flujo | Publicar los términos con la sección de señas | Founder, abogado | ABIERTO |
| H17 | C | MEDIO | El cliente no conoce antes de reservar: a quién transfiere, las indicaciones, cómo se confirma el pago, las condiciones de cancelación y devolución de la seña, ni qué pasa si no transfiere (el turno queda confirmado igual). Antes de confirmar solo ve el monto | `booking_page.html:135`; `DepositSettings` sin campos de condiciones | Ley 24.240 arts. 4 y 19; CCyC 1100, 1059 | Reclamos del cliente por una seña que no sabía que no se devolvía; el proveedor es el negocio, pero la pantalla la diseña TurnoFacil | El deber de informar es del negocio; TurnoFacil responde por cómo muestra lo que el negocio carga | Cambios de interfaz I1 a I5 de `PLAN_IMPLEMENTACION.md` (paso 7) | Founder (decisión), Builder | ABIERTO |
| H18 | C | INDETERMINADO | En la relación negocio y cliente, la reserva online es una contratación a distancia del servicio del negocio. No está claro si el negocio debe ofrecer el Botón de Arrepentimiento en su página de reservas (que provee TurnoFacil) ni cómo juega con la seña y con la excepción del servicio ya usado | Página de reservas sin botón; cancelación gratis hasta 2 h antes | Disp. 954/2025 arts. 1 y 3 b; Ley 24.240 art. 34; CCyC 1110 | Sanción al negocio y reclamo al canal | No se encontró criterio oficial para servicios con fecha fuera de espectáculos y turismo (art. 2) | Consulta al abogado; si aplica, el botón en la página de reservas es una función de TurnoFacil para los negocios | Abogado | ABIERTO |
| H19 | C | INDETERMINADO | Alcance de la responsabilidad de TurnoFacil frente al cliente final (no es proveedor del servicio, pero aporta el canal y su marca aparece en la página de reserva) | `booking_page.html` ("Reservas con TurnoFacil") | Ley 24.240 art. 40; CCyC 1073 a 1075 | Reclamo solidario por un turno o una seña | Interpretación discutible; no se buscó jurisprudencia | Consulta al abogado. Los términos no deben intentar excluir esta responsabilidad, solo describir los roles | Abogado | ABIERTO |
| H20 | C | BAJO | Los textos al cliente dicen "no verifica **automáticamente** el pago", lo que sugiere que TurnoFacil lo verifica de otra forma | `_deposit.html:11`, `confirmation.txt` | Ley 24.240 art. 4 (información cierta) | Confusión sobre quién recibe el dinero | Hecho verificado | Cambiar a "TurnoFacil no recibe el dinero ni verifica el pago" (I1) | Builder | ABIERTO |
| H21 | B | BAJO | El titular, alias, CBU/CVU y CUIT/CUIL de la cuenta del negocio se muestran a cada cliente que reserva y van en el email. Si el titular es una persona humana, son datos personales del dueño publicados por decisión suya | `_deposit.html`, `confirmation.txt` | Ley 25.326 arts. 4 y 6 | Bajo: el dueño los carga para eso y la pantalla le avisa que los ven sus clientes; el CUIT es opcional | Hecho verificado | Informarlo en la política de privacidad (hecho en el borrador) | Builder | ABIERTO |
| H22 | C | BAJO | La pantalla de cancelación y los emails de cancelación no recuerdan que la devolución de la seña depende del negocio | `cancel_confirm.html`, `emails/cancelled.txt` | Ley 24.240 art. 4 | El cliente cancela sin saber qué pasa con su seña | Hecho verificado | Línea con las condiciones del negocio y su contacto (I4) | Builder | ABIERTO |
| H12 | B | BAJO | Cookies: solo esenciales (sesión y CSRF). No requieren banner; deben informarse en la política | `settings.py`, `app.js` | Ley 25.326 (cuando identifican) | Bajo | No hay analítica ni publicidad | Sección de cookies en la política; no agregar analítica sin decisión del Founder | Builder | ABIERTO |
| H13 | A | BAJO | Dependencias con licencias permisivas; psycopg es LGPL-3.0, usado sin modificar y sin distribuir (SaaS) | `ASSET_LICENSES.md` | Licencias de cada paquete | Bajo | No hay distribución del binario | Mantener el inventario al agregar paquetes | Builder | ABIERTO |
| H14 | A | INDETERMINADO | Marca "TurnoFacil" sin búsqueda de anterioridades en el INPI | Sin evidencia | Ley 22.362 | Conflicto marcario si otro la registró | Un dominio disponible no implica marca libre | Búsqueda en el INPI antes de invertir en marca | Founder | ABIERTO |
| H15 | C | INDETERMINADO | Facturación de las suscripciones | Sin evidencia | ARCA | Incumplimiento tributario | Fuera del alcance | Consultar con contador | Founder | DERIVADO (contador) |
| H16 | C | BAJO | No se exige mayoría de edad ni capacidad para contratar | `SignupForm` | CCyC (capacidad) | Bajo | Clientes son negocios | Declaración en términos | Builder | ABIERTO |

Interpretaciones jurídicas (separadas de los hechos):
- Que TurnoFacil sea **encargado** de los datos de los clientes finales y **responsable** de los datos de los
  dueños es una lectura razonada del art. 25 de la Ley 25.326 aplicada al flujo verificado; la confirma un abogado.
- Que los negocios no sean consumidores es discutible; mientras no se resuelva, se recomienda cumplir como si lo fueran.
- Que TurnoFacil no sea proveedor de servicios de pago se apoya en un hecho verificado (no recibe ni mueve fondos
  de señas) y en fuentes secundarias sobre el régimen del BCRA; se confirma si algún día cambia el flujo.

### 7.1 Señas: qué riesgos se reducen y cuáles siguen
Revisión del 2026-10-24, con el flujo confirmado por el Founder y verificado en el código (sección 3).

| Riesgo | Antes | Ahora | Por qué |
|---|---|---|---|
| Procesar pagos de señas | Sin revisar | **Reducido: no aplica en el alcance** | No hay integración de pagos para señas |
| Recibir o custodiar dinero de clientes | Sin revisar | **Reducido: no aplica en el alcance** | El dinero va de la cuenta del cliente a la del negocio |
| Obligaciones por intermediar pagos (régimen BCRA) | Sin revisar | **Reducido**, certeza Baja | Sin fondos ni cuentas de pago; verificar si el flujo cambia |
| Guardar datos financieros de clientes | Sin revisar | **Reducido** | No se guarda nada de pago del cliente; solo datos de destino del negocio (H21) |
| Devolver señas | Sin revisar | **Traslado a cargo del negocio**, con deber de información de TurnoFacil (H17, H22) | TurnoFacil no tiene el dinero; sí diseña lo que el cliente ve |
| Responsabilidad ante cancelaciones | Sin revisar | **Abierto** (H18, H19) | Arrepentimiento en reservas online y responsabilidad del canal sin resolver |
| Descripción del flujo en documentos | H11 | **Abierto** (H11) | Borradores actualizados, sin publicar |

Ninguno se marca `RESUELTO`: los que se reducen dependen de que el flujo no cambie, y los documentos que lo
explican no están publicados.

### 7.2 Responsabilidades por relación
| Relación | Partes | Qué contrata | Quién cobra |
|---|---|---|---|
| Suscripción SaaS | TurnoFacil y el negocio | Uso de la herramienta | TurnoFacil, por Mercado Pago |
| Reserva | El negocio y su cliente (TurnoFacil provee el canal) | El servicio del negocio en un horario | Nadie en TurnoFacil |
| Seña | El cliente y el negocio | Garantía del turno, según condiciones del negocio | El negocio, por transferencia directa |

**TurnoFacil responde por:**
- El funcionamiento del sistema de reservas (horarios, no superposición, confirmaciones, recordatorios, cancelación y reprogramación).
- Mostrar con fidelidad lo que el negocio carga (monto, destino, condiciones) y no presentarse como receptor del dinero.
- El tratamiento y la protección de los datos personales que procesa (como responsable o por cuenta del negocio).
- Comunicar sus propias condiciones de uso, planes, cobro, baja y reembolsos de la suscripción.
- Que las funciones que ofrece hagan lo que dice que hacen.
- Lo que la ley le atribuya frente al cliente final, que no se excluye por contrato (H19).

**El negocio responde por:**
- Decidir si pide seña y su monto.
- Informar el monto, el destinatario y las indicaciones antes de la reserva (TurnoFacil le da dónde hacerlo).
- Cargar datos de transferencia correctos y propios.
- Definir e informar sus condiciones de cancelación, reprogramación y devolución, compatibles con los derechos del cliente.
- Confirmar la recepción del dinero con su cliente.
- Gestionar y pagar las devoluciones que correspondan.
- El servicio que presta y lo que promete en su página.

### 7.3 Estado tras la implementación (2026-10-24, rama `feat/legal-compliance`, sin desplegar)
La columna "Estado" de la tabla de hallazgos refleja la auditoría. Esta tabla dice qué cambió en el código.
Nada está en producción, así que ningún hallazgo pasa a `RESUELTO` hasta desplegar y verificar en vivo.

| Hallazgo | Implementado | Falta para cerrarlo |
|---|---|---|
| H01 | Documentos versionados e inmutables (`legal.LegalDocument`), páginas `/terminos/` y `/privacidad/`, casilla desmarcada validada en el servidor, nueva aceptación en cada versión, comando que se niega a publicar borradores | Datos del titular, texto revisado por abogado, publicar y desplegar |
| H02 | Aviso en la reserva que nombra al negocio como responsable; aviso de privacidad en el registro (sin casilla); enlaces en el pie | Publicar la política |
| H03 | Aviso al dueño al cargar turnos; comandos para exportar y borrar los datos de un negocio y de un cliente | Cláusula validada por abogado; plazo de borrado al cerrar una cuenta |
| H04 | Fuentes servidas desde el propio sitio: Google ya no recibe la IP de los visitantes (verificado en el navegador: todas las peticiones van al propio dominio) | DPA de Render, Resend y Cloudflare, o cláusulas modelo |
| H05, H06 | `/baja/` y `/arrepentimiento/` sin login, código al instante por email, efecto al confirmar desde el email, constancia, aviso al operador para reembolsos, comando `service_requests` | Abogado: si el paso de confirmación por email cuenta como "trámite adicional" y si el pie de la home es "lugar destacado" |
| H07 | Página `/contacto/` que aparece al cargar `LEGAL_CONTACT_EMAIL` | Cargar las variables `LEGAL_*` en Render |
| H09 | Comandos de acceso, supresión y depuración; `PROCEDIMIENTO_DERECHOS.md` | Plazo de conservación (`APPOINTMENT_RETENTION_DAYS`) y agregar `purge_old_data` a la tarea programada |
| H10 | `legal.LegalAcceptance`: versión exacta, hash, fecha UTC, contexto; inmutable; sin aceptaciones retroactivas | Desplegar |
| H11, H17, H20, H22 | Condiciones de la seña opcionales; bloque de seña antes de confirmar; textos "TurnoFacil no recibe el dinero ni verifica el pago"; aviso en cancelación y su email | Publicar términos con la sección 7 |
| H17 (opción B) | Marca manual "seña recibida" y aviso al cliente | — |
| H21 | Aviso al dueño en la pantalla de la seña | Publicar la política |
| H08, H14, H15, H16, H18, H19 | — | Decisiones, abogado o contador |

### 7.4 Revisión externa del PR #4 (ChatGPT, 2026-10-24) y correcciones
Hallazgos contrastados con el código. Corregidos en la misma rama, con tests en
`legal/tests/test_review_fixes.py`:

| Hallazgo de la revisión | Evaluación | Corrección |
|---|---|---|
| H-01: un arrepentimiento en plazo quedaba como "reembolso pendiente" y decía "cortamos la renovación" aunque Mercado Pago hubiera fallado | Correcto, era un error | La solicitud guarda por separado el resultado de la baja y `refund_due`. Si la baja falla queda `Revisión del operador` + reembolso pendiente; el email y el aviso al operador lo dicen. Errores inesperados del proveedor también van a revisión |
| H-02: si fallaba un email, la solicitud quedaba sin constancia ni reintento | Correcto | Se guarda cuándo salió cada email; la pantalla avisa si no salió; `service_requests` lista los fallidos y `--resend` los reenvía sin repetir la baja |
| H-03: la inmutabilidad se podía saltear con operaciones masivas | Correcto en teoría (requiere acceso al Shell) | Triggers de PostgreSQL (`legal.0003`): los documentos no se pueden modificar ni borrar; las aceptaciones no se pueden modificar y solo se borran junto con la cuenta |
| H-04: el plazo de 10 días | Correcto, y había un error más concreto: se contaban 240 horas | Se cuentan fechas calendario en hora de Argentina, a favor del consumidor; tests en el límite. Día inhábil: pregunta para el abogado |
| H-05: estados de la solicitud | Cubierto por H-01 y H-02 | — |
| H-06: borrar aceptaciones al borrar la cuenta | Decisión, no error | Pregunta para el abogado (sección 10) |
| H-09: email compartido en `customer_data` | Correcto como riesgo operativo | Paso de verificación en `PROCEDIMIENTO_DERECHOS.md` |
| Fallas de red de Mercado Pago | Ya cubierto: el adaptador las convierte en `PaymentError` (`billing/mercadopago.py:116`) | Además, cualquier otra excepción va a revisión manual |
| Confirmaciones simultáneas | Ya cubierto: la fila se bloquea (`select_for_update`) y la segunda no hace nada | Test de doble confirmación existente |
| Migraciones | Coincidimos: solo agregan | Probar `migrate` sobre una copia de la base de producción antes de desplegar (agregado a "Antes de desplegar") |

**Antes de desplegar** (además de lo de la sección 12): hacer un backup de la base en Render, restaurarlo en
una base aparte, correr `migrate` ahí y probar registro, reserva, panel, seña y planes.

## 8. Medidas recomendadas (priorizadas)
Cambios técnicos (detalle en `PLAN_IMPLEMENTACION.md`):
| Prioridad | Medida | Obligación legal o buena práctica | Hallazgo |
|---|---|---|---|
| 1 | Páginas `/terminos`, `/privacidad`, `/contacto` versionadas, servidas desde la base, con enlaces en el pie de todas las páginas | Obligación | H01, H02, H07, H12 |
| 2 | Casilla desmarcada "Acepto los Términos y Condiciones" en el registro, validada en el servidor, con registro de la aceptación; aviso de privacidad sin casilla | Obligación / probatoria | H01, H10 |
| 3 | Aviso de privacidad completo en el formulario de reserva (responsable: el negocio; TurnoFacil procesa por su cuenta) | Obligación | H02, H03 |
| 4 | Formulario público de baja y arrepentimiento con código en 24 h y efecto real | Obligación dudosa; implementación recomendada | H05, H06 |
| 5 | Fuentes servidas desde el propio dominio (sin Google Fonts) | Reduce H04 | H04 |
| 6 | Borrado de cuenta a pedido y plazos de conservación | Obligación | H03, H09 |
| 7 | Información completa de la seña antes de reservar, condiciones del negocio y textos corregidos (cambios I1 a I5) | Obligación del negocio; buena práctica de TurnoFacil | H17, H20, H22 |

Decisiones comerciales del Founder: datos del titular; plazos de conservación; reembolso voluntario (por ejemplo,
mes en curso); implementar los botones aunque se discuta su aplicabilidad; inscripción ante la AAIP.

Validaciones jurídicas: lista de la sección 10.

## 8 bis. Pruebas ejecutadas
| Prueba | Resultado | Limitaciones |
|---|---|---|
| Revisión estática del código y plantillas | Hallazgos de la sección 7 | No se navegó el sitio en producción |
| Licencias de dependencias con `importlib.metadata` en `.venv` | Django BSD-3, psycopg LGPL-3.0, gunicorn MIT, whitenoise MIT, asgiref BSD-3, sqlparse BSD, tzdata Apache-2.0 | Solo dependencias instaladas localmente |
| Licencia de las fuentes en `github.com/google/fonts` | Bricolage Grotesque y Hanken Grotesk en `ofl/` (SIL OFL 1.1) | Se leyó el encabezado del archivo |
| Señas: búsqueda de integraciones de pago, carga de archivos y llamadas HTTP en `bookings` y `businesses`; lectura de modelo, formulario, plantillas y emails de la seña | Sin integraciones; Mercado Pago solo en `billing` para la suscripción; hallazgos H17 a H22 | Revisión del código, no del sitio en vivo; no se revisó si algún negocio real tiene la seña activa |
| Implementación técnica (rama `feat/legal-compliance`) | `ruff check`, `ruff format --check` y `manage.py check` sin errores; `manage.py test`: 480 tests OK (66 nuevos en `legal/tests/` y `businesses/tests/test_deposit_legal.py`, incluidas las correcciones de la revisión en `test_review_fixes.py`) | Tests en PostgreSQL local; sin desplegar |
| Revisión visual en el navegador (vista de celular, servidor local) | Botones en el pie de la home, página de baja y bloque de seña antes de confirmar se ven bien | No se probó con lector de pantalla; los emails se vieron en los tests, no en un cliente de correo |

## 9. Preguntas pendientes
- Para el Founder: titular (persona o sociedad), CUIT, domicilio, emails; si hay DPA con proveedores; si la
  base está inscripta; plazos de conservación; si se ofrece algún reembolso voluntario.
- Para el Founder (señas): respondidas el 2026-10-24, incluida la opción B (sección 11).
- Para el Founder: ¿algún negocio que no sea el piloto tiene la seña activa hoy? Se puede revisar desde el
  Shell de Render sin modificar datos.
- Para el cliente: no aplica (producto propio).

## 10. Asuntos que requieren abogado matriculado
| Asunto | Motivo | Urgencia |
|---|---|---|
| ¿Los negocios clientes son consumidores (Ley 24.240 art. 1)? ¿Aplican los botones de la Disp. 954/2025? | Define obligaciones de baja, arrepentimiento y cláusulas | Alta |
| Rol de TurnoFacil como encargado y texto de la cláusula de tratamiento | Art. 25 Ley 25.326 | Alta |
| Transferencias a EE. UU. y Brasil: suficiencia de los DPA de los proveedores o cláusulas modelo | Art. 12 Ley 25.326 | Alta |
| Inscripción ante la AAIP | Alcance discutido de los arts. 21 y 24 | Media |
| Texto final de términos y privacidad antes de publicarlos | Riesgo de cláusulas abusivas | Alta |
| Valor probatorio de la aceptación por clic | CCyC y Ley 25.506 | Baja |
| ¿Corresponde el Botón de Arrepentimiento en las reservas online de cada negocio? ¿Cómo se combina con la seña y la excepción del servicio usado? | H18; Disp. 954/2025 | Alta |
| Responsabilidad de TurnoFacil frente al cliente final como canal (art. 40 Ley 24.240, contratos conexos) | H19 | Media |
| Qué condiciones de seña pueden fijar los negocios sin ser abusivas (pérdida de la seña por cancelar, plazos) y si TurnoFacil debe limitarlas | H17; CCyC 1059 y 1117 a 1122; Ley 24.240 art. 37 | Media |
| Confirmar que el régimen BCRA de proveedores de servicios de pago no aplica | 7.1; certeza Baja | Baja |
| ¿Confirmar la baja desde el email cuenta como "trámite adicional" (Disp. 954/2025 arts. 1 y 4)? Se agregó para que nadie dé de baja una cuenta ajena | H05, H06; 7.3 | Alta |
| ¿Los botones en el pie de la home cumplen con "lugar destacado y primer acceso"? | H05, H06 | Media |
| Plazo de arrepentimiento: ¿se corre si el día 10 es inhábil? Hoy se cuentan 10 días corridos por fecha calendario | H-04 de la revisión; 7.4 | Media |
| ¿Cuánto tiempo hay que conservar la evidencia de aceptación de una cuenta que pide ser borrada? Hoy se borra con la cuenta | H-06 de la revisión; 7.4 | Media |

## 11. Decisiones del Founder
| Hallazgo | Decisión (aceptar / mitigar / derivar) | Fecha |
|---|---|---|
| H17 | Mitigar con condiciones de la seña **opcionales** (I3). Si faltan, el cliente ve un texto neutro que le pide consultarlas. H17 sigue ABIERTO: sin condiciones, el cliente no conoce las reglas de devolución antes de transferir | 2026-10-24 |
| H17 / H20 | Agregar marca manual "seña recibida" en el panel (I6), sin verificación por parte de TurnoFacil | 2026-10-24 |
| H17 | Turno confirmado aunque no se transfiera: **opción B** de `PLAN_IMPLEMENTACION.md` (paso 7). Queda confirmado, con marca manual "seña recibida" (I6) y aviso al cliente (I7); si la seña no llega, el dueño cancela desde el panel según sus condiciones | 2026-10-24 |
| H17, H20 a H22 | Contexto: el negocio piloto no pide seña hoy, así que hoy ningún cliente está expuesto. La urgencia baja; el nivel no cambia porque cualquier negocio con plan Profesional o Negocio puede activarla | 2026-10-24 |

## 12. Estado final
- [x] `BLOCKED`   - [ ] `NEEDS_REVIEW`   - [ ] `NO_HIGH_RISK_FOUND_IN_SCOPE`

Justificación (sin cambios tras la revisión de señas del 2026-10-24: el flujo confirmado reduce los riesgos
de pagos, pero no toca H01 a H04): hallazgos ALTO abiertos (H01 a H04) sin mitigar. H04 está derivado, pero H01 a H03 requieren
cambios y datos del titular. El producto ya está en producción: el estado no apaga el sitio, pero indica que no
conviene sumar clientes pagos nuevos hasta publicar términos y privacidad validados.

Límites de esta revisión: análisis automatizado sobre el código y fuentes oficiales a la fecha; sin revisión de
contratos de proveedores ni del sitio en vivo; no reemplaza la revisión de un abogado matriculado.
