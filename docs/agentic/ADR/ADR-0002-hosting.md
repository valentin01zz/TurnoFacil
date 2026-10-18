# ADR-0002: Hosting

- Estado: aceptado (aprobado por el Founder el 2026-10-18)
- Fecha: 2026-10-18
- Decide: Founder

## Contexto
El MVP pasó el QA gate y hay que publicarlo para la estética piloto. Lo que el hosting tiene que dar:
- Un proceso Python siempre encendido (la página de reservas no puede tardar un minuto en despertar).
- PostgreSQL administrado con la extensión `btree_gist` (la usa la protección contra turnos superpuestos) y
  copias de seguridad.
- Una tarea programada cada 15 minutos para `send_reminders`.
- HTTPS y dominio propio.
- Poco trabajo de operación: lo mantiene el Founder con agentes, sin un equipo de infraestructura.

Tráfico esperado en el piloto: un negocio y sus clientes, decenas de visitas por día.

Precios consultados el 2026-10-18 en las páginas oficiales y en comparativas recientes. Pueden cambiar; se
confirman al crear la cuenta.

## Opciones consideradas
1. **Render** (plataforma administrada).
   - Costo estimado: servicio web Starter USD 7/mes (0,5 CPU, 512 MB, sin suspensión), PostgreSQL de 256 MB desde
     USD 6/mes y tarea programada con mínimo de USD 1/mes. Total aproximado: **USD 14 a 15/mes** más
     almacenamiento.
   - Pros: corre Django sin Docker, HTTPS y dominio propio incluidos, tareas programadas como servicio nativo,
     `btree_gist` figura como extensión soportada en su documentación, copias continuas con recuperación a un
     punto en el tiempo (3 días en el plan Hobby) y copias lógicas por 7 días.
   - Contras: no tiene región en Sudamérica (la más cercana es Virginia, EE. UU.). El plan gratuito no sirve: el
     servicio web se suspende tras 15 minutos sin tráfico y la base gratuita se borra a los 30 días.
2. **Railway** (plataforma administrada con cobro por uso).
   - Costo estimado: plan Hobby USD 5/mes, que funciona como mínimo de consumo; el uso real se cobra por segundo.
     Para este tráfico podría quedar cerca del mínimo, pero el monto no es fijo.
   - Pros: muy simple de usar, tareas programadas nativas (intervalo mínimo de 5 minutos), cobro por uso.
   - Contras: tampoco tiene región en Sudamérica (la más cercana es Virginia). Las copias de seguridad de
     PostgreSQL dependen de la plantilla y del plan elegidos, y no encontré documentación oficial que confirme
     `btree_gist` en la imagen estándar. Costo mensual menos predecible.
3. **Servidor propio (VPS)** con Django, PostgreSQL y cron instalados a mano.
   - Pros: el costo más bajo a mediano plazo y elección libre de región.
   - Contras: el Founder pasa a operar un servidor (actualizaciones de seguridad, copias de seguridad, certificados,
     monitoreo). Contradice el principio de simplicidad para un piloto. No coticé proveedores.

## Decisión propuesta
**Opción 1: Render**, región Virginia (EE. UU.), con tres servicios: servicio web Starter, PostgreSQL pago y una
tarea programada cada 15 minutos.

Es la opción que cumple todos los requisitos con documentación oficial (incluida `btree_gist` y las copias de
seguridad) y con costo fijo y previsible. La diferencia de precio con Railway es chica frente al riesgo de
descubrir en producción que falta una extensión o un respaldo.

## Consecuencias
- Costo de alrededor de USD 15/mes desde el primer día, más el dominio.
- Latencia desde Argentina mayor que con un servidor en la región (EE. UU. queda lejos de Buenos Aires). Para
  páginas livianas como estas no debería notarse; se mide en el piloto.
- El código necesita ajustes de producción antes del deploy, comunes a cualquier plataforma:
  - un servidor web de producción (`gunicorn`);
  - servido de archivos estáticos (`whitenoise`);
  - configuración de HTTPS y de registro de errores (pendientes del QA gate: R3 y los avisos de `check --deploy`);
  - páginas de error propias (R4).
  Son dos dependencias nuevas, justificadas porque Django no trae un servidor de producción.
- Se versiona un archivo de configuración de Render en el repo para que el deploy sea repetible.

## ¿Es reversible?
Sí, con costo bajo. La app no usa nada exclusivo de Render: mudarse es exportar la base con `pg_dump`, crear los
servicios en otra plataforma y apuntar el dominio.

## Fuentes
- Render, regiones: https://render.com/docs/regions
- Render, extensiones de PostgreSQL: https://render.com/docs/postgresql-extensions
- Render, plan gratuito: https://render.com/docs/free
- Render, copias de seguridad: https://render.com/docs/postgresql-backups
- Render, tareas programadas: https://render.com/docs/cronjobs
- Railway, regiones: https://docs.railway.com/reference/regions
- Railway, tareas programadas: https://docs.railway.com/reference/cron-jobs
- Comparativas de precios 2026: https://deployhandbook.com/pricing/render y https://livemy.app/blog/railway-pricing
