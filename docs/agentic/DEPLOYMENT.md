# Deployment: TurnoFacil / MVP

- Hosting: Render (ADR-0002). Email: Resend por SMTP (ADR-0003).
- Configuración versionada: `render.yaml` (Blueprint) en la raíz del repo.
- Servicios: `turnofacil-web` (web), `turnofacil-reminders` (tarea cada 15 minutos) y `turnofacil-db`
  (PostgreSQL 17), todos en la región Virginia.

## Antes
- [x] Informe de QA aprobado (`QA_CHECKLIST.md`, aprobado con riesgos conocidos aceptados por el Founder).
- [x] Dominio comprado: `turnofacil.online` en DonWeb (vence el 2027-10-19), con la zona DNS en DonWeb.
- [x] Variables de entorno definidas en Render (fuera del repo; ver tabla abajo).
- [x] Migraciones revisadas: se aplican solas antes de cada deploy (`preDeployCommand`). La base arranca vacía.
- [x] Rollback documentado (ver abajo).
- [x] OK del Founder: primer deploy hecho por el Founder el 2026-10-19.

## Estado actual (2026-10-19)
- En producción: https://turnofacil.online (también `www` y `turnofacil-web.onrender.com`), HTTPS emitido por Render.
- DNS en DonWeb: `A` de `turnofacil.online` a `216.24.57.1` (Render); `www` como CNAME; para Resend,
  `resend._domainkey` (TXT), `send` y `rsend` (CNAME) y `_dmarc` (TXT). DonWeb pide el nombre completo
  (por ejemplo `send.turnofacil.online`) y precarga `www.` en los CNAME: hay que borrarlo.
- Resend: dominio verificado (región São Paulo); la API key tiene solo permiso de envío.
- Costo real informado por Render: USD 17,50 por mes, más la tarea programada (se cobra por segundo).

## Lo que hace el Founder (requiere sus cuentas y medios de pago)
1. **Dominio:** comprarlo en el registrador elegido.
2. **Resend:** crear la cuenta, agregar el dominio y cargar en el DNS los registros que Resend indique (SPF y
   DKIM). Esperar a que figure como verificado. Crear una API key con permiso solo de envío.
3. **Render:** crear la cuenta (plan Hobby) y cargar un medio de pago. Conectar la cuenta de GitHub con acceso al
   repo `valentin01zz/TurnoFacil`.

## Primer deploy (Founder y Builder juntos)
1. En Render: **New > Blueprint**, elegir el repo y la rama `main`. Render lee `render.yaml` y propone los tres
   servicios.
2. Completar las variables que pide (las marcadas `sync: false`):

   | Variable | Valor | Servicios |
   |---|---|---|
   | `ALLOWED_HOSTS` | el dominio, por ejemplo `turnofacil.com.ar` | web |
   | `SITE_URL` | `https://` + el dominio, sin barra final | web y tarea |
   | `DEFAULT_FROM_EMAIL` | `TurnoFacil <no-reply@el-dominio>` | web y tarea |
   | `EMAIL_HOST_PASSWORD` | la API key de Resend | web y tarea |

   `SECRET_KEY` y `DATABASE_URL` las genera Render. El resto ya viene definido en `render.yaml`.
3. Aplicar el Blueprint. El primer build instala dependencias, junta los archivos estáticos y aplica las
   migraciones. En el primer deploy la base puede no estar lista todavía y las migraciones fallan con
   `Connection refused`: esperar a que la base figure **Available** y, en el servicio web, **Manual Deploy >
   Deploy latest commit**.
4. En el servicio web: **Settings > Custom Domains**, agregar el dominio y cargar en el DNS el registro que indica
   Render. Render emite el certificado HTTPS solo.
5. Mientras el dominio propaga, la app responde en la dirección `*.onrender.com` del servicio (se acepta sola).

## Verificación después del deploy
- [x] La portada abre por HTTPS y `http://` redirige a `https://` (2026-10-19).
- [x] Registro de un negocio de prueba con verificación de email recibida desde el dominio (2026-10-19).
- [ ] Alta de un servicio y un profesional con horarios.
- [ ] Reserva desde un celular con un email real: llega la confirmación desde el dominio propio, no a spam.
- [ ] Reprogramar y cancelar desde el link del email.
- [ ] En **Logs** de la tarea `turnofacil-reminders`: corridas cada 15 minutos con `Reminders sent: N`.
- [ ] Logs del servicio web sin errores.
- [ ] Borrar los datos de prueba y crear la cuenta real de la estética piloto.
- [ ] Darle a la estética piloto el plan sin costo: en el servicio web, **Shell**, correr
      `python manage.py grant_plan <slug-de-la-estetica> piloto` (ADR-0004).
- [ ] En **Logs** de la tarea: también aparece `Trial notices sent: N` (avisos de prueba).

## Activar Mercado Pago (HU-29 a HU-31)
Hasta hacer esto, la app sigue con el proveedor manual: se elige el plan y el pago se coordina por fuera.

1. **Founder:** en [Mercado Pago Developers](https://www.mercadopago.com.ar/developers/panel/app), crear una
   aplicación (producto: Suscripciones) con la cuenta vendedora y configurar la acreditación a 35 días.
2. **Founder:** crear dos usuarios de prueba (vendedor y comprador) en **Cuentas de prueba**. Las credenciales de
   prueba salen del vendedor de prueba.
3. **Founder:** en la aplicación, **Webhooks > Configurar notificaciones**: URL
   `https://turnofacil.online/webhooks/mercadopago/`, eventos de **Planes y suscripciones** (suscripciones y
   pagos recurrentes). Copiar la clave secreta.
4. **Founder:** en Render, en `turnofacil-web` **y** en `turnofacil-reminders`, **Environment**, agregar:

   | Variable | Valor |
   |---|---|
   | `PAYMENT_PROVIDER` | `billing.mercadopago.MercadoPagoProvider` |
   | `MERCADOPAGO_ACCESS_TOKEN` | primero el de prueba (`TEST-...` o el del vendedor de prueba), después el de producción |
   | `MERCADOPAGO_WEBHOOK_SECRET` | la clave secreta del paso 3 |
   | `TRANSFER_ALIAS`, `TRANSFER_HOLDER`, `TRANSFER_CUIT`, `BILLING_CONTACT_EMAIL` | datos de la transferencia (opcional) |

   Las credenciales nunca van al repo ni al chat.
5. **Prueba con credenciales de prueba** (Founder y QA juntos), con un negocio de prueba y el comprador de prueba:
   - [ ] Suscribirse en prueba: el checkout muestra el primer cobro al terminar la prueba; al volver, el plan
         queda activo y Planes muestra "Próximo cobro".
   - [ ] En **Logs** de `turnofacil-web`, los avisos de Mercado Pago responden 200 (no 401).
   - [ ] Suscribirse con la prueba vencida: cobra en el momento y el período pasa a un mes.
   - [ ] Cambiar de plan y dar de baja desde Planes; verificar el monto y el estado en Mercado Pago.
6. Con todo verificado, cambiar `MERCADOPAGO_ACCESS_TOKEN` por el de producción (y la clave secreta si es otra).

## Rollback
- **Código:** en el servicio web, **Events**, elegir el deploy anterior y **Rollback**. Tarda lo que un deploy
  (unos minutos). La tarea de recordatorios se revierte igual, desde su propio servicio.
- **Base de datos:** las migraciones del MVP solo agregan tablas y columnas; volver a una versión anterior del
  código no necesita tocar la base. Si un deploy futuro incluye una migración que borra o transforma datos, antes
  de desplegar se hace una copia manual (**Recovery > Export** en la base) y se documenta en este archivo.
- **Pérdida o corrupción de datos:** Render guarda copias continuas de la base paga; en el plan Hobby se puede
  restaurar a cualquier momento de los últimos 3 días (**Recovery** en la base). La restauración crea una base
  nueva; después se apunta `DATABASE_URL` a ella.
- **Desactivar Mercado Pago:** borrar `PAYMENT_PROVIDER` en Render (vuelve el proveedor manual). Las
  suscripciones ya autorizadas siguen cobrándose en Mercado Pago: darlas de baja allá si hace falta.
- **Volver a no estar publicado:** suspender el servicio web desde **Settings > Suspend**. Los datos quedan.

## Operación
- Costo esperado: unos USD 15 por mes (servicio web, base y tarea), más el dominio. Emails: USD 0 hasta 100 por día.
- HSTS arranca en 1 hora (`SECURE_HSTS_SECONDS=3600`). Cuando el dominio funcione estable por HTTPS durante unas
  semanas, subirlo a un año. No activar `includeSubDomains` ni `preload` sin revisarlo: son difíciles de revertir.
- Antes de abrir el registro a otros negocios: resolver R1 del QA gate (límite de intentos) y revisar el tope de
  100 emails por día de Resend.

## Después
- [ ] Documentación de uso entregada a la estética piloto.
- [ ] Cliente informado.
- [ ] Qué costó trabajo o se repitió → `docs/registro-de-candidatos.md` (repo NEXORA).
