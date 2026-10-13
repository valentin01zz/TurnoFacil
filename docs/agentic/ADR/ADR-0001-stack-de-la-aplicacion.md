# ADR-0001: Stack de la aplicación

- Estado: aceptado (aprobado por el Founder el 2026-10-13)
- Fecha: 2026-10-13
- Decide: Founder

## Contexto
El MVP aprobado (`PRD.md`) es una app web multi-negocio: registro e inicio de sesión del negocio, panel de
agenda, página pública de reservas usable desde el celular, emails de confirmación y un recordatorio
programado 24 horas antes. No hay código previo ni stack obligatorio.

Lo que el stack tiene que resolver bien:
- Formularios con validación en el backend y autenticación del negocio.
- Aislamiento de datos entre negocios.
- Que nunca se creen dos turnos superpuestos para el mismo profesional, aun con reservas simultáneas.
- Una tarea programada para los recordatorios.
- Poco código y pocas piezas: lo mantiene un Founder con agentes, no un equipo.

Estado de la máquina de desarrollo (verificado el 2026-10-13): Python 3.11.9 y Node 22.14 instalados.
No hay Docker ni PostgreSQL.

## Opciones consideradas
1. **Django + PostgreSQL, páginas renderizadas en el servidor.**
   - Pros: trae resueltos autenticación, ORM, migraciones, formularios con validación, envío de email, tests y
     comandos para tareas programadas. Una sola aplicación y un solo deploy. Python ya es el lenguaje de los
     proyectos anteriores del Founder. Tecnología madura y estable.
   - Contras: interfaz menos "app" que una SPA; las interacciones ricas (por ejemplo, arrastrar turnos en un
     calendario) cuestan más. Necesita un hosting que corra un proceso Python y una tarea programada.
2. **Next.js (TypeScript) + PostgreSQL.**
   - Pros: un solo lenguaje para frontend y backend, interfaz más rica, ecosistema muy grande, hosting con
     planes gratuitos.
   - Contras: autenticación, ORM, validación y email se arman con librerías separadas (más dependencias y más
     decisiones). El framework cambia seguido. Las tareas programadas dependen de las condiciones del hosting.
3. **Backend como servicio (Supabase o similar) + frontend estático.**
   - Pros: arranque muy rápido, base de datos y autenticación incluidas.
   - Contras: las reglas de negocio (superposición de turnos, límite de 2 horas, aislamiento entre negocios)
     quedan repartidas entre políticas de base de datos y funciones del proveedor, más difíciles de testear.
     Dependencia fuerte del proveedor.

## Decisión
**Opción 1: Django 5.2 LTS sobre Python 3.11, PostgreSQL y plantillas renderizadas en el servidor.**

El MVP es, en esencia, formularios, listados y emails: es el caso que Django resuelve con menos código y menos
dependencias. JavaScript se agrega solo donde una pantalla lo necesite (por ejemplo, elegir horario sin
recargar), sin framework de frontend.

Quedan fuera de este ADR y se deciden antes del primer deploy, cada una con su ADR:
- Hosting (requisito: proceso Python, PostgreSQL administrado y tarea programada).
- Proveedor de email transaccional (se integra por SMTP o API detrás del sistema de email de Django).

## Consecuencias
- Se gana: una sola base de código, autenticación y validación probadas, tests desde el primer endpoint,
  y una ruta simple para sumar WhatsApp o pagos más adelante.
- Se pierde: la interfaz será correcta y simple, no una SPA. Si en el futuro se quiere una app móvil nativa,
  habrá que exponer una API (Django lo permite, pero es trabajo adicional).
- Hay que instalar PostgreSQL en la máquina de desarrollo, o usar una base administrada para desarrollo.
  Se usa PostgreSQL también en desarrollo y tests para que el control de superposición se pruebe contra el
  mismo motor que producción.
- Riesgo: el hosting tendrá un costo mensual bajo pero no nulo; se estima en el ADR de hosting.

## ¿Es reversible?
Con costo. Antes de escribir código, cambiar es gratis. Una vez construido el MVP, cambiar de framework implica
reescribir la aplicación; los datos en PostgreSQL se conservan.
