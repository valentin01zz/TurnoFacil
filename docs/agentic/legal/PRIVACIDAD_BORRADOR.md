# BORRADOR. NO PUBLICAR.

> Borrador del Legal & Compliance Agent (2026-10-24), escrito a partir del código verificado (commit
> `33cce4f`). Antes de publicarlo: completar los `[COMPLETAR]`, aplicar los cambios técnicos que el texto da
> por hechos (marcados `> Requiere:`) y hacerlo revisar por un abogado. Si el sistema cambia, esta política
> cambia de versión.

# Política de Privacidad de TurnoFacil

Versión: 1.0 · Vigente desde: [COMPLETAR al publicar]

## 1. Quién es responsable
- **Datos de los negocios que usan TurnoFacil:** el responsable es [COMPLETAR: nombre o razón social], CUIT
  [COMPLETAR], domicilio [COMPLETAR], email [COMPLETAR].
- **Datos de las personas que reservan un turno en un negocio:** el responsable es **ese negocio**, cuyo nombre
  figura en su página de reservas. TurnoFacil trata esos datos por cuenta del negocio, solo para gestionar los
  turnos.

## 2. Qué datos tratamos, para qué y por qué
| Persona | Datos | Para qué | Base | ¿Obligatorio? |
|---|---|---|---|---|
| Dueño del negocio | Email, contraseña (guardada como hash, nunca en texto), nombre del negocio, fecha de alta, verificación del email | Crear y proteger la cuenta, avisos del servicio y de la prueba | Relación contractual (art. 5.2 d, Ley 25.326) | Sí: sin ellos no hay cuenta |
| Dueño del negocio | Servicios, horarios, profesionales (nombres) | Mostrar la página de reservas | Relación contractual | Según lo que use |
| Dueño del negocio (si pide seña) | Monto, titular de la cuenta, alias, CBU/CVU, CUIT/CUIL (opcional) e indicaciones | Mostrárselos a cada cliente que reserva, en la página del turno y en el email de confirmación, para que le transfiera la seña **directamente** | Relación contractual; el negocio decide publicarlos | Solo si activa la seña |
| Dueño del negocio | Plan, estado de la suscripción, email del pagador y referencia de Mercado Pago (no la tarjeta) | Cobrar la suscripción | Relación contractual | Solo si contrata un plan pago |
| Cliente que reserva | Nombre y apellido, teléfono, email, turno elegido | Que el negocio gestione el turno; confirmación, recordatorio y link para cambiarlo o cancelarlo | Relación con el negocio (art. 5.2 d) | Sí para reservar online |
| Cualquier visitante | Dirección IP y email ingresado, en intentos de ingreso, registro, recuperación de contraseña y reservas | Prevenir abusos (límites de intentos) | Interés en la seguridad del servicio [COMPLETAR: validar base con abogado] | Automático |

No pedimos datos sensibles. Pedimos a los negocios que no los carguen (por ejemplo, diagnósticos en el nombre
de un servicio).

No usamos los datos para publicidad, no los vendemos y no hacemos perfiles. Tampoco los usamos para
finalidades distintas ni incompatibles con las de esta tabla.

**Consentimiento:** al enviar un formulario de TurnoFacil (registro o reserva) das tu consentimiento libre,
expreso e informado para que tratemos tus datos según esta política. Darlos es voluntario, pero sin los
marcados como obligatorios no podemos crear tu cuenta ni registrar tu turno online; en ese caso podés
reservar comunicándote directamente con el negocio.

**Señas:** la seña se transfiere directamente del cliente al negocio, por fuera de TurnoFacil. No recibimos
ni guardamos datos de pago de los clientes (cuentas, tarjetas, comprobantes) ni sabemos si la transferencia se
hizo. Los datos de pago que hay en TurnoFacil son solo los de destino que carga el negocio y, para la
suscripción del negocio, la referencia de Mercado Pago.

## 3. Quién más recibe datos
| Proveedor | Qué hace | Qué datos recibe | Dónde |
|---|---|---|---|
| Render | Hosting y base de datos | Todos los datos de la app | Estados Unidos (Virginia) |
| Resend | Envío de emails | Email del destinatario y contenido del email (turno, negocio) | Brasil (São Paulo), verificado el 2026-10-26 |
| Cloudflare (a través de Render y Resend) | Red y protección | Dirección IP y datos técnicos de la conexión | Estados Unidos (según la lista de proveedores de Render) |
| Mercado Pago | Cobro de la suscripción del negocio (no interviene en las señas) | Email del pagador, plan y monto | [COMPLETAR: verificar]; trata los datos de pago según sus propias políticas |

Las tipografías se sirven desde nuestro propio sitio: ningún proveedor de fuentes recibe tu IP.

TurnoFacil guarda los datos en servidores de Render (Estados Unidos) y envía los emails a través de Resend
(Brasil). Estos países no tienen un nivel de protección de datos equivalente al de Argentina. Al aceptar esta
política, consentís expresamente esa transferencia.

## 4. Cuánto tiempo guardamos los datos
> Requiere: decisión del Founder y comando de borrado (`PLAN_IMPLEMENTACION.md`, paso 6). Hasta que existan,
> esta sección no se publica.
- Cuenta del negocio: mientras la cuenta esté activa; al cerrarla, [COMPLETAR] días.
- Turnos y datos de clientes: [COMPLETAR: por ejemplo, 12 meses después del turno], o lo que pida el negocio.
- Intentos de ingreso y registro (IP y email): 24 horas.
- Datos de facturación: lo que exija la ley tributaria.

## 5. Seguridad
Adoptamos las medidas técnicas y organizativas necesarias para garantizar la seguridad y confidencialidad de
tus datos y evitar su adulteración, pérdida, consulta o tratamiento no autorizado. Usamos conexión cifrada (HTTPS) en todo el sitio, contraseñas guardadas con hash, protección contra
falsificación de formularios, límites de intentos y separación de datos entre negocios (cada negocio ve solo
los suyos). Ningún sistema es infalible: si ocurre un incidente que afecte tus datos, te avisamos.

> Nota: no afirmar "cifrado en reposo" ni ubicación exclusiva sin verificarlo en Render.

## 6. Cookies
Usamos solo cookies necesarias para que el sitio funcione:
| Cookie | Para qué | Duración |
|---|---|---|
| `sessionid` | Mantener abierta la sesión del negocio | 2 semanas o hasta salir |
| `csrftoken` | Proteger los formularios contra falsificación | 1 año |

No usamos cookies de analítica, publicidad ni de terceros, ni almacenamiento local del navegador. Por eso no
mostramos un aviso de consentimiento de cookies. Si eso cambia, lo vamos a pedir antes de activarlas.

## 7. Tus derechos
De acuerdo con la Ley 25.326, podés pedir gratis el acceso, la rectificación, la actualización o la supresión
de tus datos. Mandá tu pedido por escrito a [COMPLETAR: email de datos personales], con una copia de tu DNI
para que podamos confirmar que sos el titular. Usamos esa copia solo para verificar tu identidad y la
borramos al cerrar el pedido.

Para pedir que borremos tus datos no hace falta escribir: usá **Eliminar mis datos**, en el pie de todas las
páginas (`/mis-datos/`). Ingresás tu email, te llega un código y un link para confirmar, y desde la
confirmación corre el plazo de 5 días hábiles. Si tenés un turno próximo, el negocio conserva tus datos hasta
que pase o lo canceles.
- Acceso: respondemos dentro de los 10 días corridos (art. 14, Ley 25.326).
- Rectificación, actualización o supresión: dentro de los 5 días hábiles (art. 16).
- Si reservaste un turno en un negocio, el responsable es el negocio: podés pedírselo a él o a nosotros, y lo
  trasladamos.

"La AGENCIA DE ACCESO A LA INFORMACIÓN PÚBLICA, en su carácter de Órgano de Control de la Ley N° 25.326,
tiene la atribución de atender las denuncias y reclamos que interpongan quienes vean afectados sus derechos
por incumplimiento de las normas vigentes en materia de protección de datos personales."

## 8. Cambios
Si cambiamos esta política, publicamos la nueva versión con su fecha y avisamos por email a los negocios.
