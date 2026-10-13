# QA Checklist: [Proyecto / versión]

## Verificaciones automáticas
- [ ] Lint
- [ ] Typecheck
- [ ] Tests (unitarios e integración)
- [ ] Build

## Criterios de aceptación
- [ ] Cada criterio de `ACCEPTANCE_CRITERIA.md` verificado

## Calidad
- [ ] Casos borde revisados
- [ ] Estados de carga / error / vacío en la UI
- [ ] Validación de inputs en el backend
- [ ] Manejo de errores y logging razonables

## Seguridad
- [ ] Sin secretos expuestos en el repo ni en logs
- [ ] Dependencias revisadas (sin innecesarias ni vulnerabilidades conocidas)
- [ ] Autenticación/autorización probadas donde aplique
- [ ] Permisos mínimos necesarios

## Resultado
- [ ] Aprobado   - [ ] Aprobado con riesgos conocidos   - [ ] Bloqueado

Problemas críticos:
Riesgos conocidos:
