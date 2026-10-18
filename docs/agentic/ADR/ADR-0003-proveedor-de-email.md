# ADR-0003: Proveedor de email

- Estado: aceptado (aprobado por el Founder el 2026-10-18)
- Fecha: 2026-10-18
- Decide: Founder

## Contexto
TurnoFacil manda cuatro emails a los clientes finales (confirmación, reprogramación, cancelación y recordatorio)
y el de recuperación de contraseña a los dueños. Hoy solo se imprimen en la consola (riesgo R7 del QA gate).

Requisitos:
- Que lleguen a la bandeja de entrada y no a spam (riesgo R1 del PRD): hace falta enviar desde un dominio propio
  con registros SPF y DKIM.
- Integración sin dependencias nuevas: Django ya trae envío por SMTP.
- Volumen del piloto: una estética, del orden de decenas de emails por día como máximo.

Precios consultados el 2026-10-18. Pueden cambiar; se confirman al crear la cuenta.

## Opciones consideradas
1. **Resend**.
   - Plan gratuito: 3.000 emails por mes con tope de 100 por día, hasta 3 dominios, SMTP incluido (confirmado en
     su página oficial de precios). Plan Pro: USD 20/mes por 50.000 emails, sin tope diario.
   - Pros: SMTP en el plan gratuito, configuración de dominio guiada, al llegar al tope frena el envío en lugar de
     cobrar excedentes.
   - Contras: el tope de 100 por día alcanza para el piloto pero no para varios negocios; ahí hay que pasar a Pro.
2. **Brevo**.
   - Plan gratuito: 300 emails por día, con envío transaccional por SMTP según varias comparativas (no pude
     confirmarlo en su página oficial). Plan pago desde unos USD 9/mes.
   - Pros: el tope gratuito diario más alto.
   - Contras: plataforma orientada a marketing, con más opciones de las que hacen falta; condiciones del plan
     gratuito sin confirmar en fuente oficial.
3. **Amazon SES**.
   - Unos USD 0,10 cada 1.000 emails.
   - Pros: el más barato cuando el volumen crece.
   - Contras: requiere una cuenta de AWS, salir del modo de prueba (sandbox) con una solicitud y más configuración.
     Demasiado para un piloto.

## Decisión propuesta
**Opción 1: Resend, plan gratuito, por SMTP**, enviando desde un dominio propio verificado (por ejemplo,
`no-reply@<dominio>`).

Cubre el piloto sin costo, se conecta con la configuración de email que Django ya tiene (solo variables de
entorno) y tiene la información clave confirmada en fuente oficial.

## Consecuencias
- **Hace falta comprar un dominio** y cargar en su DNS los registros que indique Resend. El mismo dominio sirve
  para la web (ADR-0002). Decisión pendiente del Founder: el nombre del dominio.
- Configuración solo por variables de entorno (`EMAIL_BACKEND` SMTP, servidor, usuario, clave y remitente); la
  clave de Resend nunca entra al repo.
- Tope de 100 emails por día. Con un negocio alcanza. Antes de sumar más negocios hay que revisar el volumen y
  pasar a Pro (USD 20/mes) o reevaluar.
- Si un día se supera el tope, los emails de ese día no salen; los turnos no se pierden (los envíos fallidos se
  registran, y los recordatorios no enviados se reintentan en la siguiente corrida).

## ¿Es reversible?
Sí, con costo muy bajo. Cambiar de proveedor es cambiar variables de entorno y los registros DNS.

## Fuentes
- Resend, precios: https://resend.com/pricing
- Brevo, comparativas: https://dreamlit.ai/blog/brevo-review y https://sendlayer.com/blog/best-free-smtp-servers/
- Amazon SES, precios: https://www.saaspricepulse.com/blog/amazon-ses-pricing-per-1000-emails-2026
