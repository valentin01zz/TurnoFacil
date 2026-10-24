# Procedimiento: pedidos sobre datos personales, bajas y arrepentimientos

Para el operador de TurnoFacil (hoy, el Founder). Los comandos se corren desde el Shell de Render
(`python manage.py ...`). Ninguno corre solo. Base legal: `LEGAL_REVIEW.md` (Ley 25.326 arts. 14 a 16 y 25;
Disposición 954/2025).

## 1. Plazos
| Pedido | Plazo | Desde |
|---|---|---|
| Acceso a los datos | 10 días corridos | Que llega el pedido |
| Rectificación, actualización o supresión | 5 días hábiles | Que llega el pedido |
| Código de una baja o arrepentimiento | 24 horas (se envía solo, al instante) | La solicitud en el sitio |
| Constancia de la baja | 72 horas (se envía sola al confirmar) | La confirmación |

## 2. Verificar la identidad sin pedir de más
- **Dueño de un negocio:** el pedido tiene que venir del email de la cuenta, o se le responde a ese email
  pidiendo que lo confirme. No se piden documentos.
- **Cliente que reservó un turno:** el pedido tiene que venir del email con el que reservó, o se le responde a
  ese email. Si reservó sin email (turno cargado a mano), se le pide al negocio que confirme.
- Nunca se responde a otro email ni por teléfono con datos.

## 3. Quién decide
- **Datos de la cuenta del negocio:** TurnoFacil es responsable y responde.
- **Datos de los clientes de un negocio:** el responsable es el negocio. TurnoFacil responde el pedido o lo
  traslada al negocio y le avisa al cliente. Si el cliente pide borrar un turno futuro, el negocio tiene que
  cancelarlo primero.

## 4. Comandos
| Pedido | Comando | Qué hace |
|---|---|---|
| Acceso de un negocio | `export_business_data <slug>` | JSON con cuenta, negocio, servicios, profesionales, seña, suscripción, aceptaciones y turnos. Sin contraseña |
| Acceso de un cliente | `customer_data <email>` | Solo los turnos reservados con ese email, en todos los negocios |
| Supresión de un cliente | `customer_data <email> --erase` | Borra nombre, teléfono y email de sus turnos pasados y cancelados; avisa cuántos futuros quedan |
| Supresión de un negocio | `delete_business <slug> --yes` | Borra el negocio, la cuenta y todo lo que depende. Se niega si la suscripción todavía se renueva. Exportar antes si el dueño quiere copia |
| Rectificación | El dueño corrige lo suyo desde el panel; un cliente se lo pide al negocio | — |
| Bajas y arrepentimientos pendientes | `service_requests` | Reembolsos pendientes, revisiones a mano y solicitudes sin confirmar hace más de un día |
| Cerrar uno | `service_requests --resolve <código> --note "qué se hizo"` | Lo marca resuelto |
| Depurar turnos viejos | `purge_old_data` | Borra turnos terminados hace más de `APPOINTMENT_RETENTION_DAYS` días. Sin esa variable no hace nada |

El JSON se manda al titular por email. Nunca incluye datos de otra persona.

## 5. Baja y arrepentimiento desde el sitio
1. La persona usa el botón (sin iniciar sesión) y recibe el código al instante.
2. Si el email tiene cuenta, el mismo email trae un link para confirmar (vale 3 días). Sin confirmación no
   cambia nada: así nadie da de baja una cuenta ajena.
3. Al confirmar, se corta la renovación en Mercado Pago y llega la constancia.
4. Arrepentimiento dentro de los 10 días corridos desde que contrató: además queda `Reembolso pendiente` y
   llega un aviso a `BILLING_CONTACT_EMAIL`. El operador devuelve el pago en Mercado Pago, termina el plan y
   corre `service_requests --resolve`.
5. Fuera de los 10 días se tramita como baja y el email lo explica.
6. Si Mercado Pago falla, o el plan se paga por transferencia, queda `Revisión del operador`.

Revisar `service_requests` al menos una vez por día hábil.

## 6. Registro
Cada pedido por email (acceso, supresión) se anota con fecha, quién, qué se pidió, qué se hizo y fecha de
respuesta, en un registro fuera del repo. Las bajas y arrepentimientos ya quedan registrados en la base
(`ServiceRequest`).
