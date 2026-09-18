from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from farms.permissions import any_member_required, manage_herd_required
from notifications.models import Notification
from notifications.services import notify

from .forms import LandParcelForm
from .models import LandParcel


def _tomtom_style_url():
    if not (settings.TOMTOM_API_KEY and settings.TOMTOM_STYLE_ID):
        return ''
    return (
        f'https://api.tomtom.com/style/2/custom/style/{settings.TOMTOM_STYLE_ID}.json'
        f'?key={settings.TOMTOM_API_KEY}'
    )


@any_member_required
def parcel_map(request):
    farm = request.farm
    parcels = LandParcel.objects.filter(farm=farm).select_related('block', 'created_by')
    parcels_data = [
        {
            'id': p.id,
            'name': p.name,
            'coordinates': p.coordinates,
            'area_sqm': float(p.area_sqm),
            'perimeter_m': float(p.perimeter_m),
            'block': p.block.name if p.block_id else '',
        }
        for p in parcels
    ]
    has_center = farm.latitude is not None and farm.longitude is not None
    config = {
        'styleUrl': _tomtom_style_url(),
        'center': [float(farm.longitude), float(farm.latitude)] if has_center else None,
        'canEdit': request.membership.can_manage_herd,
        'saveUrl': reverse('geomap:parcel_create'),
    }
    return render(request, 'geomap/map.html', {
        'parcels': parcels,
        'parcels_data': parcels_data,
        'config': config,
        'form': LandParcelForm(farm=farm),
    })


@manage_herd_required
def parcel_create(request):
    if request.method != 'POST':
        return redirect('geomap:map')
    form = LandParcelForm(request.POST, farm=request.farm)
    if form.is_valid():
        parcel = form.save(commit=False)
        parcel.created_by = request.user
        parcel.save()
        notify(request.farm, request.user, Notification.Verb.CREATED, 'land parcel', parcel.name)
        messages.success(request, _('"%(name)s" saved - %(area)s hectares.') % {
            'name': parcel.name, 'area': parcel.area_ha,
        })
    else:
        errors = ' '.join(e for field_errors in form.errors.values() for e in field_errors)
        messages.error(request, errors or _("Couldn't save that shape."))
    return redirect('geomap:map')


@manage_herd_required
def parcel_delete(request, parcel_id):
    parcel = get_object_or_404(LandParcel, id=parcel_id, farm=request.farm)
    if request.method == 'POST':
        name = parcel.name
        parcel.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'land parcel', name)
        messages.success(request, _('%(name)s deleted.') % {'name': name})
    return redirect('geomap:map')
