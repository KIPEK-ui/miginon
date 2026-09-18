"""Unauthenticated views for outside organizations - the self-serve half of
the data-partner onboarding flow. No login, no farm context; contrast with
views.py (farm members) and api.py (already-approved partners)."""
from django.shortcuts import render

from .forms import PartnerApplicationForm


def partner_apply(request):
    if request.method == 'POST':
        form = PartnerApplicationForm(request.POST)
        if form.is_valid():
            partner = form.save()
            return render(request, 'creditscore/partner_apply_done.html', {'partner': partner})
    else:
        form = PartnerApplicationForm()
    return render(request, 'creditscore/partner_apply.html', {'form': form})
