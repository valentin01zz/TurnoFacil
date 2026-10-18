# Graph Report - TurnoFacil  (2026-10-18)

## Corpus Check
- Corpus is ~17,452 words - fits in a single context window. You may not need a graph.

## Summary
- 648 nodes · 1510 edges · 43 communities (26 shown, 17 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 162 edges (avg confidence: 0.89)
- Token cost: 177,095 input · 0 output

## Community Hubs (Navigation)
- Availability Slot Tests
- Forms and Migrations
- Test Helpers and Modules
- Availability and Booking Forms
- Professionals Tests
- Reminder Command
- Booking Flow Tests
- Account Views and Templates
- Owner Panel Appointments
- Architecture and ADRs
- Service Tests
- Django Config Bootstrap
- User Stories and Backlog
- PRD Scope and Assumptions
- Cancellation Tests
- QA Findings and Risks
- Appointment Model
- Agenda Tests
- Business Panel Tests
- Data Schema
- HTTP Routes Spec
- Appointment Templates
- Agent Rules and README
- Customer Emails
- Django App Configs
- Signup Tests
- Auth Tests
- Password Reset Tests
- Stack and Dependencies
- Custom User Model
- Confirmation Email Tests
- Signup Form
- Panel Template

## God Nodes (most connected - your core abstractions)
1. `local_dt()` - 64 edges
2. `Appointment` - 54 edges
3. `create_appointment()` - 45 edges
4. `create_professional()` - 28 edges
5. `Business` - 26 edges
6. `create_service()` - 25 edges
7. `PanelAppointmentTests` - 25 edges
8. `create_business()` - 24 edges
9. `available_slots()` - 23 edges
10. `RescheduleTests` - 22 edges

## Surprising Connections (you probably didn't know these)
- `URL name 'appointment_create'` --references--> `appointment_create()`  [INFERRED]
  templates/businesses/panel.html → bookings/panel_views.py
- `URL name 'appointment_reschedule'` --references--> `appointment_reschedule()`  [INFERRED]
  templates/businesses/panel.html → bookings/panel_views.py
- `URL name 'appointment_cancel'` --references--> `appointment_cancel()`  [INFERRED]
  templates/businesses/panel.html → bookings/panel_views.py
- `URL name 'cancel_appointment'` --references--> `cancel_appointment()`  [INFERRED]
  templates/bookings/appointment_detail.html → bookings/views.py
- `URL name 'reschedule_appointment'` --references--> `reschedule_appointment()`  [INFERRED]
  templates/bookings/appointment_detail.html → bookings/views.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Reserva online sin superposicion** — docs_agentic_user_stories_hu_04, docs_agentic_api_spec_book_route, docs_agentic_architecture_availability_calculation, docs_agentic_architecture_exclusion_constraint_no_overlap, docs_agentic_database_schema_appointment, docs_agentic_database_schema_btree_gist_extension, docs_agentic_acceptance_criteria_reserva_simultanea_edge_case [INFERRED 0.85]
- **Flujo de recordatorio por email** — docs_agentic_user_stories_hu_08, docs_agentic_prd_supuesto_s2, docs_agentic_architecture_reminder_mechanism, docs_agentic_api_spec_send_reminders_command, docs_agentic_database_schema_appointment, docs_agentic_qa_checklist_pre_deploy_requirements [INFERRED 0.85]
- **Aislamiento multi-negocio** — docs_agentic_architecture_business_scoping_mixin, docs_agentic_acceptance_criteria_aislamiento_entre_negocios_edge_case, docs_agentic_api_spec_panel_routes, docs_agentic_database_schema_business, docs_agentic_prd_supuesto_s4 [INFERRED 0.85]
- **Password reset flow templates** — templates_accounts_password_reset_form, templates_accounts_password_reset_subject, templates_accounts_password_reset_email, templates_accounts_password_reset_done, templates_accounts_password_reset_confirm, templates_accounts_password_reset_complete [INFERRED 0.95]
- **Customer booking email notifications** — templates_bookings_emails_confirmation, templates_bookings_emails_rescheduled, templates_bookings_emails_cancelled, templates_bookings_emails_reminder, templates_concept_manage_url [INFERRED 0.95]
- **Customer self-service appointment management via manage token** — templates_bookings_appointment_detail, templates_bookings_cancel_confirm, templates_bookings_reschedule, templates_bookings_appointment_not_found, templates_bookings__appointment_summary [INFERRED 0.85]

## Communities (43 total, 17 thin omitted)

### Community 0 - "Availability Slot Tests"
Cohesion: 0.07
Nodes (9): create_appointment(), local_dt(), AvailableSlotsTests, TestCase, PanelAppointmentTests, TestCase, TestCase, RescheduleProfessionalTests (+1 more)

### Community 1 - "Forms and Migrations"
Cohesion: 0.06
Nodes (43): LoginForm, Migration, AuthenticationForm, Migration, AgendaForm, BaseWorkingHoursFormSet, Meta, ProfessionalForm (+35 more)

### Community 2 - "Test Helpers and Modules"
Cohesion: 0.13
Nodes (21): TsTzRange, create_business(), create_professional(), create_service(), future_date(), Professional working the given ranges every day of the week., SingleProfessionalBookingTests, EmailSubjectTests (+13 more)

### Community 3 - "Availability and Booking Forms"
Cohesion: 0.08
Nodes (28): available_slots(), booking_window(), First and last dates a customer can book., Start times on `date` where `service` fits in the professional's free working…, BookingDateForm, BookingForm, clean_phone(), A day inside the booking window. (+20 more)

### Community 4 - "Professionals Tests"
Cohesion: 0.11
Nodes (6): BookingPageProfessionalsTests, create_business(), professional_data(), ProfessionalTests, TestCase, Build the POST payload for the professional form and its hours formset.

### Community 5 - "Reminder Command"
Cohesion: 0.17
Nodes (9): BaseCommand, Command, due_reminders(), Send every reminder that is due and mark it, so each appointment gets at most…, send_due_reminders(), TestCase, ReminderTests, django_core_management_base (+1 more)

### Community 6 - "Booking Flow Tests"
Cohesion: 0.20
Nodes (3): AppointmentRulesTests, BookingFlowTests, TestCase

### Community 7 - "Account Views and Templates"
Cohesion: 0.13
Nodes (11): home(), signup(), django_shortcuts, Django auth form context, Django built-in auth views, URL name 'home', URL name 'login', URL name 'logout' (+3 more)

### Community 8 - "Owner Panel Appointments"
Cohesion: 0.19
Nodes (17): send_rescheduled(), PanelAppointmentForm, PanelScheduleForm, Professional, day and time chosen by the business owner (any time, not only…, agenda_url(), appointment_cancel(), appointment_create(), appointment_reschedule() (+9 more)

### Community 9 - "Architecture and ADRs"
Cohesion: 0.12
Nodes (20): Caso borde: negocio ve datos de otro -> acceso denegado, ADR-0001: Stack de la aplicacion, Backend as a service / Supabase (rejected), ADR de proveedor de email (pendiente), ADR de hosting (pendiente), Next.js + PostgreSQL (rejected), ADR template, Arquitectura: TurnoFacil (+12 more)

### Community 10 - "Service Tests"
Cohesion: 0.16
Nodes (3): create_business(), TestCase, ServiceTests

### Community 11 - "Django Config Bootstrap"
Cohesion: 0.12
Nodes (12): ASGI config for config project. It exposes the ASGI callable as a module-level…, load_env_file(), Load KEY=VALUE lines from a local .env file without overriding real env vars., WSGI config for config project. It exposes the WSGI callable as a module-level…, django_core_asgi, django_core_wsgi, main(), Django's command-line utility for administrative tasks. (+4 more)

### Community 12 - "User Stories and Backlog"
Cohesion: 0.40
Nodes (16): Criterios de aceptacion: TurnoFacil, Rutas del panel (/panel/...), Backlog: TurnoFacil, Orden de construccion del MVP, HU-01 Registro del negocio, HU-02 Servicios, HU-03 Profesionales y horarios, HU-04 Reservar un turno (+8 more)

### Community 13 - "PRD Scope and Assumptions"
Cohesion: 0.12
Nodes (16): Recordatorios via reminder_due_at / reminder_sent_at, Guardar en UTC, mostrar en zona de Argentina, Alcance del MVP, Criterios de exito, Fuera de alcance / futuro, Piloto: local de estetica, PRD: TurnoFacil, Problema: negocios pierden turnos y no ordenan reservas (+8 more)

### Community 15 - "QA Findings and Risks"
Cohesion: 0.19
Nodes (15): python manage.py send_reminders (cada 15 minutos), Campo trampa oculto contra reservas falsas, R2 Reservas falsas o abusivas, Resultado: aprobado con riesgos conocidos (151/151 tests), CUSTOMER_CHANGE_LIMIT_HOURS, Decision del Founder (2026-10-18): Opcion A, H1 Salto de linea en nombre del negocio rompe emails (BadHeaderError), H2 Texto fijo de 2 horas en recordatorio (+7 more)

### Community 16 - "Appointment Model"
Cohesion: 0.17
Nodes (5): Appointment, Meta, Customers may change a confirmed appointment until the configured limit before…, Move to a new start time (and professional), resetting the reminder., manage_url (tokenized self-service link)

### Community 18 - "Business Panel Tests"
Cohesion: 0.19
Nodes (5): BookingPageTests, BusinessSlugTests, create_business(), PanelTests, TestCase

### Community 19 - "Data Schema"
Cohesion: 0.26
Nodes (13): Link unico de gestion por turno, Caso borde: dos clientes confirman el mismo horario, Restriccion de exclusion PostgreSQL contra superposicion, Appointment (bookings), Extension btree_gist de PostgreSQL, Business (businesses), Professional, Esquema de datos: TurnoFacil (+5 more)

### Community 20 - "HTTP Routes Spec"
Cohesion: 0.18
Nodes (13): Rutas de cuenta (/signup/, /login/, /logout/, /password-reset/), POST /b/<slug>/book/, GET /b/<slug>/ pagina de reservas, /t/<token>/cancel/, POST con validacion backend y CSRF, GET /t/<token>/ gestion del turno, /panel/appointments/ new, reschedule, cancel, El panel reprograma y cancela sin el limite de 2 horas (+5 more)

### Community 21 - "Appointment Templates"
Cohesion: 0.31
Nodes (5): appointment context object, URL name 'appointment_detail', URL name 'cancel_appointment', URL name 'panel', URL name 'reschedule_appointment'

### Community 22 - "Agent Rules and README"
Cohesion: 0.17
Nodes (12): Agentes activos (PO, Architect, Builder, QA/SecOps), Cliente ideal (peluquerias, barberias, estetica, kinesiologos, talleres), Founder authority, FOUNDER DECISION REQUIRED format, NEXORA system, Reglas esenciales, STATUS report format, TurnoFacil AGENTS.md (+4 more)

### Community 23 - "Customer Emails"
Cohesion: 0.24
Nodes (8): Email the customer about their appointment. Returns whether it was sent; never…, send_cancelled(), send_confirmation(), send_customer_email(), send_reminder(), django_core_mail, django_template_loader, logging

### Community 24 - "Django App Configs"
Cohesion: 0.20
Nodes (7): AccountsConfig, AppConfig, BookingsConfig, AppConfig, BusinessesConfig, AppConfig, django_apps

### Community 28 - "Stack and Dependencies"
Cohesion: 0.31
Nodes (7): Comandos de lint/test/check/runserver, Django 5.2 LTS + PostgreSQL server-rendered (chosen), Estructura: config, accounts, businesses, bookings, Una sola app Django, sin colas ni cache ni frontend separado, ruff, Django >=5.2,<5.3, psycopg[binary] >=3.2,<4

### Community 29 - "Custom User Model"
Cohesion: 0.25
Nodes (5): AbstractBaseUser, User, UserManager, BaseUserManager, django_contrib_auth_models

### Community 32 - "Panel Template"
Cohesion: 0.40
Nodes (4): business context object, URL name 'appointment_cancel', URL name 'appointment_create', URL name 'appointment_reschedule'

## Knowledge Gaps
- **26 isolated node(s):** `Migration`, `Migration`, `TsTzRange`, `Meta`, `Migration` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 166 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Appointment` connect `Appointment Model` to `Availability Slot Tests`, `Forms and Migrations`, `Test Helpers and Modules`, `Availability and Booking Forms`, `Panel Template`, `Reminder Command`, `Booking Flow Tests`, `Owner Panel Appointments`, `Cancellation Tests`, `Agenda Tests`, `Data Schema`, `Appointment Templates`, `Customer Emails`, `Confirmation Email Tests`?**
  _High betweenness centrality (0.413) - this node is a cross-community bridge._
- **Why does `Appointment (bookings)` connect `Data Schema` to `Appointment Model`, `PRD Scope and Assumptions`?**
  _High betweenness centrality (0.221) - this node is a cross-community bridge._
- **Why does `Business` connect `Test Helpers and Modules` to `Forms and Migrations`, `Availability and Booking Forms`, `Professionals Tests`, `Service Tests`, `Appointment Model`, `Business Panel Tests`, `Data Schema`, `Signup Tests`, `Auth Tests`, `Signup Form`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `Appointment` (e.g. with `available_slots()` and `Business`) actually correct?**
  _`Appointment` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `create_appointment()` (e.g. with `Appointment` and `.test_database_allows_back_to_back_and_cancelled_overlaps()`) actually correct?**
  _`create_appointment()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `create_professional()` (e.g. with `Professional` and `WorkingHours`) actually correct?**
  _`create_professional()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `Business` (e.g. with `SignupForm` and `AuthTests`) actually correct?**
  _`Business` has 12 INFERRED edges - model-reasoned connections that need verification._