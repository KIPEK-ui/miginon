from django.shortcuts import render

from farms.permissions import any_member_required

from .models import FarmInsight
from .services import refresh_insights

_SEVERITY_ORDER = {FarmInsight.Severity.CRITICAL: 0, FarmInsight.Severity.WARNING: 1, FarmInsight.Severity.INFO: 2}


@any_member_required
def overview(request):
    insights = sorted(refresh_insights(request.farm), key=lambda i: (_SEVERITY_ORDER[i.severity], i.title))
    return render(request, 'insights/overview.html', {'insights': insights})
