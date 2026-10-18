# Deployment: TurnoFacil / MVP

- Hosting: Render (ADR-0002). Email: Resend por SMTP (ADR-0003).
- Configuración versionada: `render.yaml` (Blueprint) en la raíz del repo.
- Servicios: `turnofacil-web` (web), `turnofacil-reminders` (tarea cada 15 minutos) y `turnofacil-db`
  (PostgreSQL 17), todos en la región Virginia.

## Antes
- [x] Informe de QA aprobado (`QA_CHECKLIST.md`, aprobado con riesgos conocidos aceptados por el Founder).
- [ ] Dominio comprado (decisión pendiente del Founder).
- [ ] Variables de entorno definidas (fuera del repo; ver tabla abajo).
- [x] Migraciones revisadas: se aplican solas antes de cada deploy (`preDeployCommand`). La base arranca vacía.
- [x] Rollback documentado (ver abajo).
- [ ] OK del Founder.

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
   migraciones.
4. En el servicio web: **Settings > Custom Domains**, agregar el dominio y cargar en el DNS el registro que indica
   Render. Render emite el certificado HTTPS solo.
5. Mientras el dominio propaga, la app responde en la dirección `*.onrender.com` del servicio (se acepta sola).

## Verificación después del deploy
- [ ] La portada abre por HTTPS y `http://` redirige a `https://`.
- [ ] Registro de un negocio de prueba, alta de un servicio y un profesional con horarios.
- [ ] Reserva desde un celular con un email real: llega la confirmación desde el dominio propio, no a spam.
- [ ] Reprogramar y cancelar desde el link del email.
- [ ] En **Logs** de la tarea `turnofacil-reminders`: corridas cada 15 minutos con `Reminders sent: N`.
- [ ] Logs del servicio web sin errores.
- [ ] Borrar los datos de prueba y crear la cuenta real de la estética piloto.

## Rollback
- **Código:** en el servicio web, **Events**, elegir el deploy anterior y **Rollback**. Tarda lo que un deploy
  (unos minutos). La tarea de recordatorios se revierte igual, desde su propio servicio.
- **Base de datos:** las migraciones del MVP solo agregan tablas y columnas; volver a una versión anterior del
  código no necesita tocar la base. Si un deploy futuro incluye una migración que borra o transforma datos, antes
  de desplegar se hace una copia manual (**Recovery > Export** en la base) y se documenta en este archivo.
- **Pérdida o corrupción de datos:** Render guarda copias continuas de la base paga; en el plan Hobby se puede
  restaurar a cualquier momento de los últimos 3 días (**Recovery** en la base). La restauración crea una base
  nueva; después se apunta `DATABASE_URL` a ella.
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
