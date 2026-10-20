"""Explicit catalog of features a plan can grant. Plans list these codes; views check them."""

# Gated: the code checks these before letting an action through.
BOOKING_ONLINE = "booking.online"  # the public page takes new bookings
PANEL_EDIT = "panel.edit"  # create, edit, reschedule and cancel from the panel
BOOKING_DEPOSIT = "booking.deposit"  # ask customers for a deposit by bank transfer

# Descriptive: features every plan includes today, shown on the plans page.
BOOKING_EMAILS = "booking.emails"
BOOKING_SELF_SERVICE = "booking.self_service"
AGENDA_CHART = "agenda.chart"

FEATURES = {
    BOOKING_ONLINE: "Página de reservas online para tus clientes",
    BOOKING_EMAILS: "Confirmación y recordatorio por email",
    BOOKING_SELF_SERVICE: "Tus clientes reprograman o cancelan solos",
    PANEL_EDIT: "Gestión de servicios, profesionales y turnos",
    AGENDA_CHART: "Agenda del día con gráfico semanal",
    BOOKING_DEPOSIT: "Seña por transferencia al reservar",
}

# Features every plan includes. The others go only to some plans, granted by data migrations.
ALL_FEATURES = [code for code in FEATURES if code != BOOKING_DEPOSIT]
# Plans with the deposit (billing migration 0004).
DEPOSIT_PLAN_CODES = ("profesional", "negocio")


def feature_labels(codes):
    return [FEATURES[code] for code in FEATURES if code in codes]
