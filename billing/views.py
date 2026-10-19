from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import get_access
from .catalog import feature_labels
from .models import Plan
from .payments import get_provider
from .services import InvalidTransition, PlanLimitExceeded, choose_plan


def plan_cards(access):
    cards = []
    for plan in Plan.objects.filter(is_public=True):
        cards.append(
            {
                "plan": plan,
                "features": feature_labels(plan.features),
                "is_current": access.plan is not None
                and access.plan.pk == plan.pk
                and not access.in_trial,
                "is_selected": access.subscription is not None
                and access.subscription.selected_plan_id == plan.pk,
                "fits": access.active_professionals <= plan.max_professionals,
                "excess": max(0, access.active_professionals - plan.max_professionals),
            }
        )
    return cards


@login_required
def plans(request):
    access = get_access(request.user.business)
    return render(
        request,
        "billing/plans.html",
        {"access": access, "cards": plan_cards(access), "trial_days": settings.TRIAL_DAYS},
    )


@login_required
@require_POST
def choose(request, code):
    plan = get_object_or_404(Plan, code=code, is_public=True)
    access = get_access(request.user.business)
    if access.subscription is None:
        messages.error(request, "No encontramos tu suscripción. Escribinos para revisarlo.")
        return redirect("plans")
    try:
        subscription = choose_plan(access.subscription, plan)
    except PlanLimitExceeded as error:
        messages.error(
            request,
            f"El plan {plan.name} permite hasta {plan.max_professionals} profesional"
            f"{'es' if plan.max_professionals != 1 else ''} activo"
            f"{'s' if plan.max_professionals != 1 else ''}. Tenés {error.active_professionals}: "
            f"desactivá {error.excess} para elegirlo.",
        )
        return redirect("plans")
    except InvalidTransition:
        messages.error(request, "No pudimos cambiar tu plan ahora. Probá de nuevo en un rato.")
        return redirect("plans")
    result = get_provider().start_checkout(subscription, plan)
    if result.redirect_url:
        return redirect(result.redirect_url)
    messages.success(request, result.message)
    return redirect("plans")
