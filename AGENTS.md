# AGENTS.md: TurnoFacil

Este proyecto se desarrolla con el sistema NEXORA. Las reglas globales están en el repo NEXORA
(`AGENTS.md`, `agents/`, `workflows/`); resumen operativo abajo. Si hay conflicto, manda este archivo
para lo específico del proyecto y NEXORA para las reglas generales.

## Contexto del proyecto
- Cliente: producto propio de NEXORA (microapp para comercializar). Cliente ideal: peluquerías, barberías, centros de estética, kinesiólogos y talleres.
- Objetivo: estos negocios pierden turnos y no logran organizar sus reservas; TurnoFacil les da una forma simple de tomarlas y gestionarlas.
- Alcance inicial indicado por el Founder (a refinar en el PRD): página de reservas, recordatorios, reprogramación y panel simple.
- Stack: Django 5.2 LTS (Python 3.11) + PostgreSQL, páginas renderizadas en el servidor. Ver `docs/agentic/ADR/ADR-0001-stack-de-la-aplicacion.md`. Hosting y proveedor de email: pendientes, con ADR propio antes del primer deploy.
- Cómo correr: lint / typecheck / tests / build: pendiente hasta que exista el stack.

## Idioma
Documentación y comunicación con el Founder en español. Código, nombres técnicos y commits en inglés.

## Reglas esenciales
1. Inspeccionar el repo antes de escribir código; no asumir tecnologías instaladas.
2. Cambios pequeños, trazables y reversibles. No borrar archivos importantes sin explicar.
3. ADR antes de decisiones arquitectónicas importantes (`docs/agentic/ADR/`).
4. Secretos en variables de entorno; nunca en el repo.
5. Validar inputs en el backend. Todo endpoint nuevo con tests.
6. Lint, typecheck, tests y build antes de dar algo por terminado.
7. Causa raíz antes de parchear.
8. No inventar requisitos del cliente. No agregar dependencias innecesarias.
9. Incertidumbre importante → `FOUNDER DECISION REQUIRED` (Decisión, Opciones, Recomendación, Impacto, Riesgo).
10. Al terminar una tarea: `STATUS: DONE / BLOCKED / NEEDS_REVIEW` con Completed, Changed, Tests, Risks, Next.

## Agentes activos
Product Owner, System Architect, Builder Full-Stack, QA/SecOps. Especialistas solo por necesidad real y con aprobación del Founder.

## Founder
Autoridad final sobre alcance, prioridades, presupuesto, stack con razón comercial y decisiones irreversibles.
