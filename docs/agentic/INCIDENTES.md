# Incidentes: qué hacer cuando "TurnoFácil no anda"

Guía corta para diagnosticar en minutos y avisar a los negocios sin tecnicismos. Nació del incidente del
2026-11-10 (el sitio no cargaba desde Movistar Argentina; ver "DNS en Cloudflare" en `DEPLOYMENT.md`).

## 1. Diagnóstico en 2 minutos
Hacer en este orden y anotar qué pasa en cada paso:

1. **¿Carga desde otra red?** Abrir `https://turnofacil.online` con los datos del celular y, si se puede, desde
   otra compañía (Claro, Personal) o el wifi de otra persona.
   - Carga en una red y en otra no: es un problema de ruta de ese proveedor, no de la app. Ir al paso 3.
2. **¿Responde Render directo?** Abrir `https://turnofacil-web.onrender.com/healthz/`.
   - `{"status": "ok"}`: la app y la base andan. El problema está entre el dominio y el cliente (DNS o ruta).
   - `{"status": "fail"}` (503): la app no llega a la base. Revisar la base en el panel de Render.
   - No responde: el servicio está caído. Revisar **Events** y **Logs** del servicio web en Render.
3. **¿Hay un problema conocido?** Mirar https://status.render.com y https://www.cloudflarestatus.com.
4. **¿Qué dicen las alertas?** UptimeRobot (app del celular) y el chequeo desde Movistar de la PC
   (`C:\Users\gilva\Documents\monitor-turnofacil\check.log`).

Con eso alcanza para saber si es "la app", "la base", "Render", "Cloudflare/DNS" o "un proveedor de internet".
Avisar a los negocios (sección 2) **antes** de ponerse a arreglar si el problema va a durar más de unos minutos.

## 2. Mensajes para los negocios
Los envía el Founder (WhatsApp o mail). Completar lo que está entre corchetes y borrar lo que no aplique.
Nunca decir "estuvo caído" si la app anduvo y el problema fue de conexión: decir lo que realmente pasó.

### Mientras dura el problema
> Hola! Estamos al tanto de que TurnoFácil **no está cargando para algunas personas** (por ahora, [con internet
> de Movistar / en general]). Ya lo estamos resolviendo.
>
> Tus turnos y datos están a salvo. Si necesitás entrar urgente, probá desde otra conexión (otro wifi o los
> datos del celular).
>
> Te aviso apenas esté solucionado.

### Cuando se resuelve
> Listo, TurnoFácil ya funciona normal. Perdón por la molestia. [Fue un problema de [conexión / servidor], ya
> está solucionado.] Si tus clientes no pudieron reservar en ese rato, pueden hacerlo ahora.

### Para que el negocio se lo pase a sus clientes (si hace falta)
> Si tuviste problemas para reservar tu turno hoy, ya está solucionado. Podés reservar de nuevo desde el mismo
> link. ¡Disculpá la molestia!

## 3. Después del incidente
- Anotar en `DEPLOYMENT.md` (o en este archivo, abajo) la fecha, qué pasó, la causa y qué se cambió.
- Si se tocó algo en Render, Cloudflare o DonWeb, dejar escrito cómo volver atrás.

## Registro
| Fecha | Qué pasó | Causa | Qué se hizo |
|---|---|---|---|
| 2026-11-10 | El sitio "se quedaba cargando" desde Movistar (wifi y datos) | La IP fija de Render para el dominio raíz (`216.24.57.1`) no era accesible desde Movistar Argentina | DNS a Cloudflare con CNAME aplanado a Render; chequeo desde la PC; alertas push de UptimeRobot |
