# PRD: TurnoFacil

- Estado: aprobado por el Founder (alcance del MVP, 2026-10-13)
- Fecha: 2026-10-13

## 1. Problema
Los negocios chicos de servicios toman turnos por teléfono, WhatsApp o cuaderno. Pierden turnos (clientes que
se olvidan o no avisan) y no logran tener las reservas ordenadas en un solo lugar.

## 2. Usuario
- **Negocio (dueño o encargado):** peluquerías, barberías, centros de estética, kinesiólogos y talleres. Uno o
  varios profesionales. Gestiona todo desde el celular o una PC, sin conocimientos técnicos.
- **Cliente final:** persona que quiere reservar un turno en ese negocio. Entra desde un link, casi siempre
  desde el celular, y no quiere crear una cuenta.

## 3. Objetivo del MVP
Que un negocio pueda registrarse, compartir un link y recibir reservas ordenadas por profesional, y que sus
clientes reciban un recordatorio y puedan reprogramar o cancelar solos.

## 4. Alcance del MVP (incluido)
- Una sola app multi-negocio: cada negocio se registra y recibe su propio link público de reservas.
- Configuración del negocio: servicios (nombre y duración) y profesionales con sus horarios de atención.
- Agenda por profesional: un negocio con un profesional tiene un calendario; con N profesionales, N calendarios.
- Página pública de reservas sin registro del cliente: elige servicio, profesional, día y hora, y deja sus datos.
- Email de confirmación con un link personal para reprogramar o cancelar.
- Reprogramación y cancelación por el cliente desde ese link.
- Recordatorio automático por email antes del turno.
- Panel simple del negocio: ver la agenda, cargar un turno a mano, reprogramar y cancelar turnos.

## 5. Fuera de alcance / futuro
- Recordatorios automáticos por WhatsApp.
- Pagos o seña.
- Cobro de suscripción a los negocios (planes, facturación).
- Bloqueo de días u horarios puntuales (feriados, vacaciones).
- Avisos al negocio por email ante cada reserva o cambio.
- Opción "cualquier profesional disponible".
- Cuentas de cliente final e historial de turnos.
- Varias sucursales por negocio, estadísticas y reportes.

## 6. Supuestos
S1, S2, S3 y S8 fueron confirmados por el Founder (2026-10-13); se revisan solo si un negocio lo pide. S4 a S7
quedaron dentro del alcance aprobado sin confirmación explícita.
- S1. (Confirmado) El cliente deja **nombre, teléfono y email**. El email es obligatorio porque el recordatorio del MVP es por email.
- S2. El recordatorio se envía 24 horas antes del turno.
- S3. El cliente puede reprogramar o cancelar hasta 2 horas antes del turno.
- S4. El negocio inicia sesión con email y contraseña; un solo usuario por negocio.
- S5. Los profesionales no tienen usuario propio: los administra el dueño.
- S6. Mercado inicial Argentina: español, una sola zona horaria.
- S7. Durante el MVP el uso es gratuito para los negocios.
- S8. Cargar turnos a mano desde el panel entra en el MVP, para que los turnos tomados por teléfono no generen
  superposiciones.

## 7. Riesgos y preguntas abiertas
- **P1 (resuelta):** el Founder decidió email obligatorio al reservar.
- **P2 (resuelta):** hay un local de estética disponible como piloto del MVP.
- **P3 (resuelta):** el Founder confirmó S2, S3 y S8 sin cambios.
- R1. Entregabilidad: los emails pueden caer en spam y el recordatorio pierde efecto.
- R2. Reservas falsas o abusivas, porque no hay cuenta ni verificación del cliente.
- R3. Datos personales de clientes finales (nombre, teléfono, email): aplica la Ley 25.326 de Argentina.
- R4. Sin bloqueo de días puntuales, el negocio no puede cerrar la agenda un feriado salvo cargando turnos a mano.

## 8. Criterios de éxito
- Un negocio nuevo queda listo para recibir reservas (registro, servicios, profesionales, horarios) en menos de 15 minutos.
- Un cliente completa una reserva desde el celular en menos de 1 minuto.
- No se generan dos turnos superpuestos para el mismo profesional.
- El negocio piloto usa TurnoFacil para sus turnos reales durante al menos dos semanas.

## 9. Restricciones (plazo, presupuesto, tecnología obligatoria)
- Plazo y presupuesto: sin definir por el Founder.
- Tecnología: sin stack obligatorio; lo propone el Architect con ADR. Se empieza de cero.

## 10. Cambio de alcance aprobado (2026-10-18)
Tras ver el MVP construido, el Founder aprobó sumar al MVP, antes del piloto:
- Diseño visual propio (propuesta "el turno es un ticket", acento turquesa #2EC4B6 y violeta #6E4BFF), aplicado a
  todas las pantallas sin cambiar la lógica.
- Dirección del negocio, cargada por el dueño y visible para el cliente.
- Elección de día con una tira de los días del mes, en lugar del campo de fecha.
- Gráfico semanal de turnos en la agenda del panel.
Historias HU-17 a HU-20.
