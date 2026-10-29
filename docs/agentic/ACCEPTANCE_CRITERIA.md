# Criterios de aceptación: TurnoFacil

Cada criterio debe poder verificarse con sí/no. Los marcados con (S#) dependen de un supuesto del `PRD.md`.

## HU-01: Registro del negocio
- [ ] Dado un visitante, cuando se registra con nombre del negocio, email y contraseña válidos, entonces queda creado el negocio y entra al panel.
- [ ] Dado un negocio registrado, cuando entra al panel, entonces ve su link público de reservas y puede copiarlo.
- [ ] Dado un negocio registrado, cuando cierra sesión y vuelve a ingresar con su email y contraseña, entonces accede a su panel.
- [ ] Caso borde: email ya registrado → el registro se rechaza con un mensaje claro.
- [ ] Caso borde: un negocio autenticado intenta ver datos de otro negocio → acceso denegado.

## HU-02: Servicios
- [ ] Dado el dueño en el panel, cuando crea un servicio con nombre y duración en minutos, entonces aparece en la página pública de reservas.
- [ ] Dado un servicio existente, cuando el dueño lo edita o lo desactiva, entonces el cambio se refleja en la página pública y los turnos ya tomados no se modifican.
- [ ] Caso borde: duración vacía, cero o negativa → no se guarda y se muestra el error.

## HU-03: Profesionales y horarios
- [ ] Dado el dueño en el panel, cuando crea un profesional con nombre y horarios de atención por día de la semana, entonces ese profesional tiene su propia agenda.
- [ ] Dado un negocio con un solo profesional, cuando un cliente reserva, entonces no se le pide elegir profesional.
- [ ] Dado un negocio con más de un profesional, cuando un cliente reserva, entonces debe elegir uno y solo ve los horarios de ese profesional.
- [ ] Caso borde: hora de fin anterior o igual a la de inicio → no se guarda y se muestra el error.
- [ ] Caso borde: negocio sin profesionales o sin servicios cargados → la página pública indica que todavía no se pueden tomar reservas.

## HU-04: Reservar un turno
- [ ] Dado un cliente en el link público, cuando elige servicio, profesional y día, entonces ve solo horarios libres, dentro del horario de atención y con lugar para la duración del servicio.
- [ ] Dado un horario libre, cuando el cliente completa nombre, teléfono y email (S1) y confirma, entonces el turno queda creado y ve una pantalla de confirmación.
- [ ] Dado un turno creado, cuando otro cliente consulta ese profesional y ese día, entonces ese horario ya no aparece disponible.
- [ ] Caso borde: dos clientes confirman el mismo horario al mismo tiempo → solo uno obtiene el turno y el otro recibe un mensaje para elegir otro horario.
- [ ] Caso borde: datos faltantes o email con formato inválido → el backend rechaza la reserva aunque el formulario no lo haya detectado.
- [ ] Caso borde: fechas u horas pasadas → no se ofrecen ni se aceptan.
- [ ] La reserva completa puede hacerse desde un celular sin crear una cuenta.

## HU-05: Confirmación por email
- [ ] Dado un turno creado, cuando se confirma la reserva, entonces el cliente recibe un email con negocio, servicio, profesional, día y hora.
- [ ] El email incluye un link único de gestión que permite reprogramar o cancelar ese turno y ningún otro.
- [ ] Caso borde: un link de gestión inexistente o alterado → se muestra "turno no encontrado" sin exponer datos.

## HU-06: Reprogramar
- [ ] Dado un cliente en su link de gestión, cuando elige un nuevo horario libre y confirma, entonces el turno se mueve, el horario anterior queda libre y recibe un email con los datos nuevos.
- [ ] Dado un turno reprogramado, cuando llega el momento del recordatorio, entonces se envía según la nueva fecha y no según la anterior.
- [ ] Caso borde: faltan menos de 2 horas para el turno (S3) → no se permite reprogramar y se indica contactar al negocio.
- [ ] Caso borde: turno ya cancelado o pasado → no se permite reprogramar.

## HU-07: Cancelar
- [ ] Dado un cliente en su link de gestión, cuando cancela y confirma, entonces el turno queda cancelado y el horario vuelve a estar disponible.
- [ ] Dado un turno cancelado, cuando llega el momento del recordatorio, entonces no se envía.
- [ ] Caso borde: faltan menos de 2 horas para el turno (S3) → no se permite cancelar desde el link.
- [ ] Caso borde: cancelar un turno ya cancelado → se informa que ya estaba cancelado, sin error.

## HU-08: Recordatorio por email
- [ ] Dado un turno confirmado, cuando faltan 24 horas (S2), entonces el cliente recibe un email con los datos del turno y el link de gestión.
- [ ] Cada turno recibe como máximo un recordatorio, aunque el proceso de envío se ejecute más de una vez.
- [ ] Caso borde: turno reservado con menos de 24 horas de anticipación → no se envía recordatorio (ya recibió la confirmación).

## HU-09: Ver la agenda
- [ ] Dado el dueño en el panel, cuando elige un día, entonces ve los turnos de ese día con hora, cliente, teléfono, servicio y profesional.
- [ ] Dado un negocio con varios profesionales, cuando el dueño filtra por uno, entonces ve solo los turnos de ese profesional.
- [ ] Los turnos cancelados no aparecen como activos en la agenda.
- [ ] El panel se puede usar desde un celular.

## HU-10: Gestionar turnos desde el panel
- [ ] Dado el dueño en el panel, cuando carga un turno a mano con cliente, servicio, profesional, día y hora (S8), entonces el turno aparece en la agenda y ese horario deja de ofrecerse en la página pública.
- [ ] Dado un turno existente, cuando el dueño lo reprograma o cancela, entonces la agenda y la disponibilidad pública se actualizan, y el cliente recibe un email si el turno tiene email cargado.
- [ ] Caso borde: cargar a mano un turno que se superpone con otro del mismo profesional → se rechaza con un mensaje claro.

## HU-17: Dirección del negocio
- [ ] Dado el dueño en el panel, cuando carga o cambia la dirección del negocio, entonces queda guardada y la ve al volver.
- [ ] Dado un negocio con dirección, cuando un cliente abre la página de reservas, entonces ve la dirección.
- [ ] Dado un negocio con dirección, cuando se envía la confirmación o el recordatorio, entonces el email incluye la dirección.
- [ ] Caso borde: negocio sin dirección → la página y los emails no muestran un espacio vacío.
- [ ] Caso borde: un dueño no puede ver ni cambiar los datos de otro negocio.

## HU-18: Tira de días del mes
- [ ] Dado un cliente en la página de reservas, cuando elige servicio y profesional, entonces ve los días del mes en una tira y puede pasar al mes siguiente o volver al anterior.
- [ ] Solo se pueden elegir días dentro de la ventana de reserva (de hoy a 60 días) en los que el profesional elegido atiende; el resto aparece deshabilitado.
- [ ] Dado un día elegido, cuando el cliente lo toca, entonces ve los horarios libres de ese día.
- [ ] Caso borde: no se puede navegar a meses fuera de la ventana de reserva.
- [ ] La reprogramación usa la misma tira de días.

## HU-19: Gráfico semanal en la agenda
- [ ] Dado el dueño en la agenda, cuando mira un día, entonces ve un gráfico con la cantidad de turnos confirmados de cada día de esa semana (lunes a domingo).
- [ ] El día que se está viendo aparece destacado y cada barra lleva a la agenda de ese día.
- [ ] Si hay un filtro por profesional, el gráfico cuenta solo los turnos de ese profesional.
- [ ] No cuenta turnos cancelados ni turnos de otros negocios.

## HU-20: Diseño visual
- [ ] Todas las pantallas (portada, reservas, turno, panel, formularios, errores) usan el mismo sistema visual.
- [ ] Al confirmar una reserva, la página del turno muestra el sello de confirmación.
- [ ] Las pantallas se usan bien en un celular de 375 px de ancho.
- [ ] Las animaciones se desactivan si el dispositivo pide reducir movimiento.
- [ ] El contraste de textos cumple 4.5:1 (3:1 en textos grandes).
- [ ] Todos los tests existentes siguen pasando.

## HU-21: Catálogo de planes
- [ ] Existen los planes Esencial (ARS 14.900, 1 profesional), Profesional (ARS 24.900, 5) y Negocio (ARS 39.900, 15).
- [ ] Precio y límite de un plan se pueden cambiar con un comando, sin desplegar código, y el cambio se ve en la pantalla de planes.
- [ ] Las funcionalidades de cada plan salen de un catálogo explícito; no se muestran funciones que no existen.

## HU-22: Prueba gratuita
- [ ] Al registrar un negocio empieza una prueba de 14 días (valor configurable) sin pedir tarjeta; inicio y fin quedan guardados.
- [ ] El fin se calcula en el servidor; ningún dato enviado por el navegador cambia fechas, estado ni permisos.
- [ ] Durante la prueba el negocio tiene los permisos y el límite del plan Profesional.
- [ ] Un negocio tiene una sola prueba; no se puede reiniciar ni duplicar desde la app.
- [ ] El panel muestra los días restantes y la fecha de finalización.
- [ ] Los negocios que ya existían reciben una prueba de 14 días desde la migración.

## HU-23: Estados de suscripción y acceso
- [ ] Estados: prueba activa, prueba vencida, pago pendiente, activa, pago con problemas y cancelada; solo se pasa de uno a otro por transiciones permitidas, registradas con su motivo.
- [ ] Con prueba vencida, pago pendiente fuera de la prueba, pago con problemas vencida la gracia, o cancelada: el panel queda en solo lectura y la página pública no toma reservas nuevas.
- [ ] En solo lectura, el dueño ve agenda, servicios, profesionales y planes, pero no puede crear, editar, reprogramar ni cancelar (validado en el servidor, también con envíos directos).
- [ ] Los turnos ya tomados se respetan: el cliente puede ver y cancelar su turno y recibe el recordatorio.
- [ ] Nunca se borran negocios, profesionales ni turnos por cambios de estado.
- [ ] Un negocio no puede ver ni cambiar la suscripción de otro.

## HU-24: Límite de profesionales
- [ ] No se puede crear ni reactivar un profesional si se alcanzó el límite del plan efectivo (validado en el servidor).
- [ ] No se puede elegir un plan cuyo límite es menor que los profesionales activos; se informa cuántos hay que desactivar.
- [ ] Si un negocio queda por encima del límite, nada se borra: se informa y solo se bloquea agregar o reactivar.

## HU-25: Pantalla de planes
- [ ] Muestra nombre, precio mensual, moneda, funcionalidades, límite de profesionales y diferencias de cada plan.
- [ ] Muestra la duración de la prueba, el estado actual, la fecha de fin de la prueba y el plan elegido.
- [ ] Permite elegir o cambiar de plan; elegir no marca la suscripción como paga.
- [ ] Usa el copy aprobado y el diseño actual, y funciona en un celular.

## HU-26: Avisos de vencimiento
- [ ] El dueño recibe un email 7, 3 y 1 día antes del fin de la prueba y otro al finalizar.
- [ ] Cada aviso se envía una sola vez aunque la tarea corra varias veces; si la tarea estuvo caída, se envía solo el aviso más urgente.
- [ ] No se envían avisos de prueba a negocios con suscripción activa.

## HU-27: Interfaz de pagos
- [ ] La elección de plan pasa por una interfaz de proveedor de pagos; sin proveedor configurado, queda como pago pendiente y se informa el siguiente paso.
- [ ] Solo una confirmación del proveedor puede activar una suscripción.
- [ ] TurnoFacil no guarda datos de tarjetas ni de medios de pago.

## HU-28: Verificación de email
- [ ] Al registrarse, el dueño recibe un email con un link firmado que vence a los 3 días; la cuenta queda sin verificar.
- [ ] Hasta confirmar, el panel solo muestra la pantalla de confirmación (con reenvío limitado a uno por minuto) y la página pública no toma reservas.
- [ ] Al confirmar empieza la prueba de 14 días; confirmar de nuevo no la reinicia.
- [ ] Un link alterado, falsificado o vencido se rechaza sin verificar la cuenta.
- [ ] No se puede abrir otra cuenta con un alias del mismo buzón (mayúsculas, "+etiqueta", puntos en Gmail).
- [ ] Las cuentas que ya existían quedan verificadas por la migración.

## HU-29: Suscribirse con Mercado Pago
- [ ] Elegir un plan lleva a una página que muestra el precio, la fecha del primer cobro y pide el email de la
      cuenta de Mercado Pago; el pago se hace en el checkout oficial de Mercado Pago.
- [ ] Durante la prueba, el primer cobro es el día que termina la prueba; sin prueba vigente, es en el momento.
- [ ] Empezar el checkout no activa nada. La suscripción se activa solo cuando Mercado Pago la autoriza, y cada
      cobro aprobado paga un mes desde la fecha del cobro.
- [ ] Cada aviso de Mercado Pago se acepta solo con firma válida, y el estado se lee siempre de la API de Mercado
      Pago con las credenciales propias; repetir un aviso no cambia nada.
- [ ] Un cobro rechazado o no confirmado un día después del vencimiento pasa a "pago con problemas", con 3 días
      de gracia; un cobro aprobado posterior lo reactiva.
- [ ] Si Mercado Pago no responde, no se cambia nada y se informa al dueño; si se pierde un aviso, la tarea
      programada lo detecta.
- [ ] TurnoFacil no guarda datos de tarjetas ni credenciales; las credenciales están solo en variables de entorno.

## HU-30: Dar de baja o cambiar de plan pagando
- [ ] La baja pide confirmación, cancela el cobro en Mercado Pago y mantiene el plan hasta el fin del mes pago;
      después la cuenta queda en solo lectura, sin borrar nada.
- [ ] Una baja hecha desde Mercado Pago se refleja igual.
- [ ] Después de una baja se puede volver a suscribir; el primer cobro nuevo es al terminar el tiempo ya pago.
- [ ] Cambiar de plan pagando es inmediato y actualiza el precio en Mercado Pago desde el próximo cobro; no se
      puede pasar a un plan más chico que los profesionales activos.

## HU-31: Pago por transferencia
- [ ] Si está configurado el alias, la página de planes muestra alias, titular, CUIT y a dónde mandar el
      comprobante; si no, no muestra nada.
- [ ] El operador activa el mes con `grant_plan <slug> <plan> --months 1`; si el negocio ya tenía tiempo pago,
      el mes nuevo se suma al final.
- [ ] `grant_plan` se niega a otorgar un plan a quien ya paga con cobro automático, para no cobrarle dos veces.

## HU-13: Bloquear días u horarios puntuales
- [ ] El dueño crea un bloqueo con fecha desde, fecha hasta (opcional, por defecto la misma), horario opcional y
      motivo opcional, para todo el negocio o para un profesional activo.
- [ ] Sin horario, el bloqueo cubre los días completos; con horario, va desde la hora de inicio del primer día
      hasta la hora de fin del último. Ambas horas o ninguna.
- [ ] No se aceptan bloqueos que terminan en el pasado, que terminan antes de empezar ni de más de 366 días.
- [ ] Mientras dura el bloqueo, la página de reservas y la reprogramación no ofrecen esos horarios; un día sin
      ningún horario libre por bloqueos aparece deshabilitado en la tira de días.
- [ ] El servidor rechaza una reserva en un horario bloqueado aunque se fuerce el envío del formulario.
- [ ] Los turnos ya confirmados en ese período no se cancelan solos. Al crear el bloqueo, el dueño los ve
      listados y elige: dejarlos o cancelar los que marque, con un motivo opcional (hasta 200 caracteres).
- [ ] Cada cliente con email recibe el aviso de cancelación, con el motivo si se cargó; el motivo privado del
      bloqueo nunca llega al cliente. A los turnos sin email (o si falla el envío) se le pide al dueño avisar
      por teléfono.
- [ ] Solo se pueden cancelar turnos confirmados de ese negocio que caen dentro del bloqueo; un turno ya
      cancelado no se vuelve a avisar.
- [ ] El dueño ve sus bloqueos vigentes y futuros y puede borrarlos; no ve ni borra los de otro negocio.
- [ ] El motivo no se muestra a los clientes. Con la cuenta en solo lectura no se crean ni borran bloqueos.
- [ ] La agenda del panel avisa cuando el día que se está viendo tiene bloqueos.

## HU-14: Aviso al negocio ante cada reserva o cambio
- [ ] Cuando un cliente reserva desde la página del negocio, el dueño recibe un email con cliente, teléfono,
      email (si lo dejó), servicio, profesional, día, hora y un link a la agenda de ese día.
- [ ] Cuando un cliente reprograma desde su link, el email muestra el horario (y profesional) anterior y el nuevo.
- [ ] Cuando un cliente cancela desde su link, el dueño recibe el aviso de cancelación.
- [ ] Lo que hace el propio dueño desde el panel (cargar, reprogramar, cancelar, cancelar por bloqueo) no le
      genera aviso.
- [ ] El aviso va al email de la cuenta del dueño solo si está verificado.
- [ ] Si el envío falla, la reserva, el cambio o la cancelación del cliente se guardan igual.

## HU-32: Escribirle al cliente por WhatsApp con un toque
- [ ] El email de "Nueva reserva" al dueño trae un link "Confirmarle por WhatsApp" que abre el chat con el
      cliente y un mensaje de confirmación ya escrito (negocio, servicio, profesional, día, hora y dirección).
- [ ] En la agenda, cada turno confirmado que todavía no terminó tiene un botón de WhatsApp con un mensaje de
      recordatorio ya escrito.
- [ ] Nada se envía solo: el dueño revisa el mensaje y lo manda desde su propio WhatsApp. TurnoFacil no manda
      datos a Meta ni paga mensajes.
- [ ] Los teléfonos argentinos se pasan al formato de WhatsApp (549 + característica + número, sin 0 ni 15);
      los que empiezan con + y otro código de país se usan tal cual. Si el número no se puede interpretar con
      seguridad (por ejemplo, sin característica), no se muestra el link.
- [ ] El mensaje nunca incluye el link privado del cliente para gestionar su turno.

## HU-33: Precio del servicio
- [ ] El precio es opcional, en pesos, mayor a cero y con hasta dos decimales. Sin precio, todo funciona como antes.
- [ ] Cada turno guarda el precio que tenía el servicio cuando se reservó (online o a mano). Cambiar el precio
      después no cambia los turnos ya tomados; reprogramar tampoco lo cambia.
- [ ] En "Mi negocio" hay una casilla "Mostrar precios a mis clientes", apagada por defecto.
- [ ] Con la casilla prendida, la página de reservas muestra el precio de los servicios que lo tienen; apagada,
      no muestra ninguno.
- [ ] El dueño ve el precio en su lista de servicios y en cada turno de la agenda.
- [ ] Revisión legal pendiente: si se muestran, que sean precios finales en pesos (Ley 24.240).

## HU-34: Marcar si el cliente asistió
- [ ] En la agenda, cada turno confirmado que ya empezó tiene los botones "Asistió" y "No asistió"; un toque lo
      marca y tocar el botón marcado lo deja otra vez sin marcar.
- [ ] No se pueden marcar turnos futuros, cancelados ni de otro negocio, aunque se fuerce el pedido; con la
      cuenta en solo lectura se ve la marca pero no se cambia.
- [ ] La agenda del día muestra cuántos asistieron, cuántos no asistieron y cuántos faltan marcar.
- [ ] Si el turno se cancela o se reprograma, la marca se borra.
- [ ] Al cliente no se le avisa nada: es un registro interno del dueño.

## HU-35: Panel de ingresos y reportes
- [ ] La pestaña "Reportes" se filtra por período (esta semana, este mes, mes anterior, últimos 3 meses) y por
      profesional, y compara con el período anterior de igual duración.
- [ ] Ingresos separados: cobrado estimado (turnos "Asistió" × su precio guardado), por confirmar (turnos ya
      empezados sin marcar) y agendado (turnos futuros del período). Los turnos sin precio cuentan como turnos
      pero no suman, y se avisa cuántos servicios activos no tienen precio.
- [ ] Turnos: asistieron, no asistieron (con su porcentaje sobre los marcados) y cancelados (con su porcentaje).
- [ ] Ranking por profesional y por servicio; demanda por día de la semana y por hora; clientes nuevos y que
      vuelven, reconocidos por su teléfono.
- [ ] "Exportar a Excel" baja los turnos del período y del filtro (fecha, hora, cliente, teléfono, email,
      servicio, profesional, precio, estado, asistencia, origen) en un CSV que Excel abre en español con doble
      clic. Las celdas que empiezan con = + - @ se escapan para que Excel no las ejecute como fórmulas.
- [ ] Solo el dueño ve los reportes de su negocio. En planes sin reportes, la pestaña explica qué incluye y lleva
      a "Ver planes", y la exportación no se puede bajar aunque se fuerce el pedido.
- [ ] Se habla de "ingresos estimados": la pantalla aclara que no son comprobantes fiscales.

