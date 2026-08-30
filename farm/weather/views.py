from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from farms.permissions import any_member_required

from .services import fetch_forecast, get_forecast_summary


@any_member_required
def forecast_view(request):
    farm = request.farm
    forecast = get_forecast_summary(farm)
    return render(request, 'weather/forecast.html', {'farm': farm, 'forecast': forecast})


@any_member_required
def refresh_view(request):
    if request.method != 'POST':
        return redirect('weather:forecast')
    farm = request.farm
    if farm.latitude is None or farm.longitude is None:
        messages.error(request, _("Weather isn't available yet for this farm."))
    elif fetch_forecast(farm, force=True):
        messages.success(request, _('Weather refreshed.'))
    else:
        messages.error(request, _("Couldn't reach the weather service. Please try again shortly."))
    return redirect('weather:forecast')
