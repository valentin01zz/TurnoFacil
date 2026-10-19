# QA Checklist: TurnoFacil / MVP (commit 09ff956)

- Fecha: 2026-10-18
- Conduce: QA/SecOps (workflow 04 de NEXORA)
- Alcance: las 10 historias del MVP (HU-01 a HU-10)

## Verificaciones automáticas
- [x] Lint: `ruff check` sin errores; `ruff format --check` sin cambios (63 archivos).
- [x] Typecheck: no aplica (el MVP no usa typecheck, decisión aprobada en `ARCHITECTURE.md`).
- [x] Tests: 148 de 148 OK contra PostgreSQL 18 (unitarios e integración con el cliente HTTP de Django).
- [x] Build: no aplica (sin paso de build). `manage.py check` sin problemas y sin migraciones pendientes.
- [x] `manage.py check --deploy` con `DEBUG=false`: 4 avisos de HTTPS (ver "Requisitos antes del deploy").

## Criterios de aceptación
- [x] Los 37 criterios de `ACCEPTANCE_CRITERIA.md` verificados.
  - 34 cubiertos por tests automáticos (cada criterio tiene al menos un test con nombre equivalente).
  - 3 verificados a mano durante la construcción: copiar el link público (HU-01), reserva completa desde el
    celular (HU-04) y panel usable desde el celular (HU-09), en vista de 375 px de ancho.

## Calidad
- [x] Casos borde: turnos simultáneos (restricción de exclusión en la base), horas pasadas, ventana de 60 días,
  límite de 2 horas, turnos cancelados o pasados, reenvíos dobles, links alterados.
- [x] Estados vacío y error en la UI: agenda sin turnos, negocio que todavía no toma reservas, sin horarios libres,
  turno no encontrado, mensajes de validación en todos los formularios.
- [x] Validación de inputs en el backend: todos los formularios validan del lado del servidor; probado con envíos
  que saltean el formulario.
- [~] Manejo de errores y logging: los fallos de email se registran y no rompen la operación. Ver R3: con
  `DEBUG=false` y la configuración por defecto de Django, los errores 500 no quedan registrados en ningún lado.

## Seguridad
- [x] Sin secretos en el repo: `.env` nunca se commiteó; la única coincidencia es una contraseña de prueba en los tests.
- [x] Dependencias: 2 directas de ejecución (Django 5.2.18, psycopg 3.3.6) y 1 de desarrollo (ruff).
  `pip-audit`: sin vulnerabilidades conocidas.
- [x] Autenticación y autorización: todas las vistas del panel exigen sesión; cada vista que recibe un id filtra
  por el negocio del usuario (404 para datos ajenos, con tests por vista). Links de gestión con token aleatorio
  de 256 bits.
- [x] Pruebas manuales de ataque: HTML escapado (nombre de negocio, servicio, profesional y cliente con
  `<script>`), CSRF exigido en formularios públicos y de ingreso, sin redirección abierta en el ingreso,
  sin SQL crudo, sin `|safe` ni `mark_safe`.
- [x] Permisos mínimos: el usuario de base de datos es dueño solo de su base y no es superusuario.

## Resultado
- [ ] Aprobado   - [x] Aprobado con riesgos conocidos   - [ ] Bloqueado

Problemas críticos: ninguno.

### Hallazgos (vuelven al Builder)
- **H1. Salto de línea en el nombre del negocio bloquea todos sus emails** (severidad media).
  El registro acepta un nombre con salto de línea si se envía armado a mano (un navegador normal no lo permite).
  Como el nombre va en el asunto, cada email de ese negocio falla con `BadHeaderError`; el error queda en el log
  pero el cliente no recibe nada. Reproducido. Corrección sugerida: rechazar o limpiar saltos de línea en el
  nombre del negocio al registrarse.
- **H2. El email de recordatorio dice "hasta 2 horas antes" fijo** (severidad baja).
  Si se cambia `CUSTOMER_CHANGE_LIMIT_HOURS`, el texto queda desactualizado. Corrección sugerida: tomar el valor
  de la configuración.

### Riesgos conocidos (decide el Founder)
- **R1. Sin límite de intentos** en ingreso, recuperación de contraseña y reservas. Permite probar contraseñas
  por fuerza bruta, inundar de emails de recuperación y cargar reservas falsas (el campo trampa solo frena bots
  simples). Mitigación posible: límite por IP; agrega una dependencia o código propio.
- **R2. El registro revela si un email ya tiene cuenta** ("Ya existe una cuenta con ese email"). Patrón habitual,
  bajo impacto.
- **R3. Errores 500 sin registro en producción.** Con la configuración de logging por defecto y `DEBUG=false`,
  Django no imprime los errores de servidor. Se resuelve configurando `LOGGING` en el deploy.
- **R4. Páginas de error genéricas** (404 y 500 por defecto de Django, en inglés), salvo "Turno no encontrado".
- **R5. Botón "Copiar" del link** usa la API del portapapeles, que solo funciona con HTTPS (o en local). Sin
  HTTPS el botón no copia, aunque el link se puede seleccionar a mano.
- **R6. No se puede borrar un negocio con turnos** (lo bloquea la protección de profesionales y servicios).
  Sin impacto mientras no exista "borrar cuenta".
- **R7. Emails solo por consola** hasta definir el proveedor (ADR pendiente).

### Decisión del Founder (2026-10-18)
Opción A: corregir H1 y H2 ahora; aceptar R1 solo para el piloto (resolver antes de abrir el registro a otros
negocios); resolver R3, R4 y R5 en el deploy; aceptar R2 y R6. R7 se resuelve con el ADR de email.

### Re-verificación tras las correcciones (2026-10-18)
- **H1: corregido.** El registro junta saltos de línea, tabulaciones y espacios repetidos en un solo espacio, y
  además todo asunto de email se manda en una sola línea. Re-probado contra la base de desarrollo con el mismo
  envío armado a mano: el nombre se guarda en una línea y el email sale. Tests nuevos para ambos casos.
- **H2: corregido.** El recordatorio toma el límite de `CUSTOMER_CHANGE_LIMIT_HOURS`. Test nuevo con otro valor.
- Lint, formato, `check` y migraciones sin problemas; 151 de 151 tests OK.

Resultado final: **aprobado con riesgos conocidos** (R1 a R7), cero problemas críticos ni hallazgos abiertos.

### Ajustes de producción (2026-10-18, verificados por QA)
- R3 resuelto: `LOGGING` manda advertencias y errores 500 a la consola (probado: un 500 forzado quedó en el log).
- R4 resuelto: páginas 404 y 500 propias en español (con tests).
- R5 resuelto: el botón "Copiar" usa un método alternativo cuando no hay HTTPS (con test).
- `check --deploy` con `DEBUG=false`: quedan solo `SECURE_HSTS_INCLUDE_SUBDOMAINS` y `SECURE_HSTS_PRELOAD`,
  apagados a propósito (difíciles de revertir; se revisan con el dominio estable).
- Modo producción probado en local: archivos estáticos versionados y comprimidos por whitenoise, cookies
  `Secure`, cabeceras de seguridad, dominios ajenos rechazados con 400 y conexión por `DATABASE_URL`.
- No probado en local: `gunicorn` (no corre en Windows); se verifica en el primer deploy.

### Requisitos antes del deploy (no bloquean este gate, sí el workflow 05)
- Activar HTTPS y las opciones que marca `check --deploy`: `SECURE_SSL_REDIRECT` (o el equivalente del hosting),
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` y `SECURE_HSTS_SECONDS` (empezar con un valor bajo).
- Configurar `ALLOWED_HOSTS`, `SITE_URL`, `SECRET_KEY` propio y `DEBUG=false` en el entorno de producción.
- Programar `manage.py send_reminders` cada 15 minutos.
- Configurar `LOGGING` (R3) y el servido de archivos estáticos.

### R1 resuelto (2026-10-19)
Límites guardados en la base (`accounts/throttle.py`, tabla `Attempt`), compartidos por todos los procesos y sin
dependencias nuevas:

| Acción | Límite | Respuesta al superarlo |
|---|---|---|
| Ingreso fallido | 10 por cuenta (email canónico) y 30 por IP en 15 minutos | Mensaje de bloqueo; ni la contraseña correcta entra hasta que pase la ventana |
| Recuperar contraseña | 3 por cuenta y 10 por IP por hora | La misma pantalla de "te enviamos un email", sin enviarlo (no revela nada) |
| Registro | 5 cuentas por IP por hora | 429 con mensaje |
| Reserva online | 20 por IP por hora | 429 con mensaje; las reservas rechazadas no cuentan |

Un ingreso correcto borra los fallos de esa cuenta. Límites conocidos: la IP sale de `X-Forwarded-For` y se puede
falsear, por eso el límite principal del ingreso es por cuenta; quien conozca un email puede bloquear esa cuenta
15 minutos (aceptado: el dueño puede recuperar la contraseña o esperar). 15 tests en
`accounts/tests/test_throttle.py`.

