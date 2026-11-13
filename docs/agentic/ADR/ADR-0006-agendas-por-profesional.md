# ADR-0006: Agendas separadas por profesional (perfiles con PIN)

- Estado: propuesto
- Fecha: 2026-11-13
- Decide: Founder

## Contexto
Un consultorio de podología con dos profesionales quiere usar TurnoFacil. Comparten el consultorio y a veces
atienden a la misma hora, pero **uno no tiene por qué ver los turnos del otro**. Los dos comparten su link de
reservas y los dos gestionan su agenda.

Hoy el panel tiene un solo usuario (el dueño de la cuenta) que ve y gestiona todo el negocio. Los profesionales
son solo nombres con horarios.

Decisiones del Founder (2026-11-13):
- Acceso con **perfiles con PIN** dentro de la cuenta del negocio.
- El **dueño** administra el negocio (servicios, plan y pago, seña, datos, profesionales) y ve todas las agendas.
- **Link de reservas propio** por profesional, además del link general.
- Los avisos de reservas, cambios y cancelaciones van **al profesional del turno**.
- Lo de datos de salud en negocios como podología no se deriva al abogado.

## Opciones consideradas
1. **Usuario propio por profesional** (email y contraseña, invitación del dueño). Es la separación más fuerte,
   pero suma invitaciones, verificación de cada usuario y roles; más trabajo y más pasos para el negocio.
2. **Perfiles con PIN en la misma cuenta.** Se entra con el usuario del negocio y se elige el perfil
   ("Mariano", "María" o "Dueño"), con un PIN de 4 a 6 números por perfil. Más simple para negocios chicos que
   comparten un dispositivo. Más débil: quien sepa el PIN ajeno ve esa agenda.
3. **Perfiles sin PIN.** Solo ordena la vista; no separa nada. Descartado: no cumple "uno no tiene por qué ver
   los turnos del otro".

## Decisión
Opción 2, elegida por el Founder. Funciona así:

- **Se activa por negocio.** En "Mi negocio", el dueño prende "Agendas separadas por profesional" y define su
  PIN. Apagado, todo sigue como hoy (el piloto no cambia nada).
- **Elegir perfil.** Con la opción prendida, después de iniciar sesión el panel pide elegir perfil y su PIN.
  El perfil queda en la sesión hasta salir o tocar "Cambiar de perfil".
- **PIN** de 4 a 6 números, guardado con hash como las contraseñas, nunca en texto. Lo define el dueño para cada
  profesional y el profesional lo puede cambiar después. Con 5 intentos fallidos el perfil se bloquea 15 minutos
  (mismo sistema de límites que el login). Cambiar un PIN cierra ese perfil en las sesiones abiertas.
- **Qué ve un profesional:** solo sus turnos en la agenda, los reportes y la exportación; carga, reprograma,
  cancela, marca asistencia y bloquea días solo para sí mismo. No ve ni toca servicios, plan, seña, datos del
  negocio ni a los otros profesionales. Todo se controla en el servidor, no solo ocultando botones.
- **Qué ve el dueño:** todo, como hoy, con el filtro por profesional.
- **Link propio:** `/b/<negocio>/<profesional>/` muestra solo a ese profesional. El link general sigue igual.
- **Avisos:** cada profesional puede tener su email. Los avisos de sus turnos le llegan **solo después de que
  confirme ese email** con un link (para que un email mal escrito no reciba datos de pacientes). Sin email
  confirmado, el aviso va al dueño, como hoy.

## Consecuencias
- Se gana: consultorios y equipos que no comparten agendas pueden usar una sola cuenta y un solo plan.
- Riesgo: el PIN es más débil que un usuario propio. Se mitiga con límite de intentos, hash y cierre de sesión al
  cambiar el PIN. Si un negocio pide separación fuerte, se suma la opción 1 más adelante sin tirar esto.
- Datos nuevos: email de cada profesional (con confirmación). Se agrega a la política de privacidad.
- Más superficie de permisos: cada vista del panel necesita su test de "un profesional no ve lo de otro".

## ¿Es reversible?
Sí. La opción se apaga por negocio y el panel vuelve a funcionar como hoy. Los campos nuevos quedan sin uso.
