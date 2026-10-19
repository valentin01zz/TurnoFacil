# ADR-0005: Proveedor de pagos para las suscripciones

- Estado: aceptado (Founder, 2026-10-18: Mercado Pago Suscripciones a 35 días + transferencia manual)
- Fecha: 2026-10-18
- Decide: Founder

## Contexto
Los planes ya existen (ADR-0004), pero el cobro es manual. El Founder pidió el proveedor que menos comisión
cobre, para quedarse con el neto más alto posible. Requisitos: cobro mensual recurrente en pesos argentinos,
checkout oficial del proveedor (TurnoFacil no toca datos de tarjetas) y notificaciones confiables para activar
la suscripción.

Comisiones consultadas el 2026-10-18. Cambian seguido y no incluyen IVA ni el impuesto provincial (Ingresos
Brutos), que depende de la provincia y de la situación fiscal del Founder.

## Opciones consideradas
1. **Mercado Pago, Suscripciones.** Cobro automático mensual con tarjeta de crédito, débito o dinero en cuenta;
   el cliente no necesita cuenta de Mercado Pago. Comisión según cuándo se acredita la plata
   (página oficial de suscripciones): al instante 6,99% + IVA; a 10 días 4,49% + IVA; a 18 días 3,39% + IVA;
   **a 35 días 1,49% + IVA**. API documentada (`preapproval`) y notificaciones por webhook.
2. **Transferencia bancaria o a alias (CBU/CVU).** Sin comisión del proveedor. Totalmente manual: el negocio
   transfiere, el Founder controla el ingreso y activa el mes con `grant_plan --months 1`. Sin renovación
   automática: depende de que cada negocio se acuerde de pagar.
3. **Débito automático por CBU o DEBIN con un agregador (ePagos, SIRO u otros).** Comisiones generalmente más bajas
   que la tarjeta, pero alta más burocrática, contrato con el agregador y sin precios públicos: hay que pedir
   cotización. Tiene sentido con más volumen.
4. **Stripe.** No está pensado para cobrar en pesos a clientes argentinos desde una cuenta argentina; descartado.

## Decisión propuesta
**Mercado Pago Suscripciones con acreditación a 35 días (1,49% + IVA, alrededor de 1,8% total antes de Ingresos
Brutos)**, más la **transferencia bancaria como alternativa manual sin comisión** para quien la prefiera.

- Es el cobro automático más barato verificado y casi todos los negocios argentinos ya conocen Mercado Pago.
- Ninguna opción automática es sin comisión. Con un plan de ARS 24.900, la comisión a 35 días ronda ARS 450 por
  mes; al instante, ronda ARS 2.100.
- Esperar 35 días no afecta el uso: la suscripción se activa cuando Mercado Pago confirma el cobro; lo que demora
  es solo que la plata quede disponible en la cuenta del Founder.

## Consecuencias
- Implementar `MercadoPagoProvider` sobre la interfaz existente (`billing/payments.py`): crear la suscripción y
  redirigir a su checkout, webhook verificado e idempotente, y el mapeo de eventos a estados (detalle en
  `PLANES_MIGRACION_Y_PAGOS.md`).
- El Founder necesita una cuenta de Mercado Pago como vendedor, configurar la acreditación a 35 días y cargar las
  credenciales en Render. Las credenciales nunca entran al repo.
- Facturación: Mercado Pago no emite la factura fiscal del Founder; hay que resolverla aparte.

## ¿Es reversible?
Sí. La interfaz de proveedor permite cambiar o sumar otro (por ejemplo, débito por CBU) sin tocar la lógica de
planes.

## Fuentes
- Mercado Pago, Suscripciones (comisiones y medios de pago): https://www.mercadopago.com.ar/herramientas-para-vender/suscripciones
- Mercado Pago Developers, Suscripciones: https://www.mercadopago.com.ar/developers/es/docs/subscriptions/overview
- Cobro recurrente en Argentina (débito por CBU y alternativas): https://yo-facturo.com/blog/cobro-recurrente-suscripciones/
- ePagos, débito automático: https://www.epagos.com/productos/opciones-de-debito-automatico.php
