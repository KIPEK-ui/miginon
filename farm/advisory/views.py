from django.shortcuts import get_object_or_404, render

from farms.permissions import any_member_required

from .models import DiseaseCatalog, Guide
from .services import nearest_agri_centers


@any_member_required
def home(request):
    return render(request, 'advisory/home.html', {
        'dairy_disease_count': DiseaseCatalog.objects.filter(category=DiseaseCatalog.Category.DAIRY).count(),
        'crop_disease_count': DiseaseCatalog.objects.filter(category=DiseaseCatalog.Category.CROP).count(),
        'guide_count': Guide.objects.count(),
    })


@any_member_required
def disease_list(request):
    category = request.GET.get('category', '')
    diseases = DiseaseCatalog.objects.all()
    if category in DiseaseCatalog.Category.values:
        diseases = diseases.filter(category=category)
    return render(request, 'advisory/disease_list.html', {
        'diseases': diseases,
        'category': category,
        'categories': DiseaseCatalog.Category.choices,
    })


@any_member_required
def disease_detail(request, disease_id):
    disease = get_object_or_404(DiseaseCatalog, id=disease_id)
    return render(request, 'advisory/disease_detail.html', {'disease': disease})


@any_member_required
def guide_list(request):
    category = request.GET.get('category', '')
    guides = Guide.objects.all()
    if category in Guide.Category.values:
        guides = guides.filter(category=category)
    return render(request, 'advisory/guide_list.html', {
        'guides': guides,
        'category': category,
        'categories': Guide.Category.choices,
    })


@any_member_required
def guide_detail(request, guide_id):
    guide = get_object_or_404(Guide, id=guide_id)
    return render(request, 'advisory/guide_detail.html', {'guide': guide})


@any_member_required
def agri_centers(request):
    return render(request, 'advisory/agri_centers.html', {
        'results': nearest_agri_centers(request.farm),
        'farm': request.farm,
    })
