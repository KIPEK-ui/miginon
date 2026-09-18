from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from farms.permissions import any_member_required, edit_delete_required, manage_records_required
from notifications.models import Notification
from notifications.services import notify

from .forms import FarmSiteForm, OrderEnquiryForm, ProductForm, SitePageForm
from .models import FarmSite, Order, Product, SitePage

# --------------------------------------------------------------- CMS (farm-scoped)

# A brand-new site starts with these pages already in place (a real starting
# point to edit, not a blank sidebar) - order matches Template's natural
# reading order. Kept as plain dicts so create() below can stamp farm.name
# into the headline without a template-rendering step.
_STARTER_PAGES = [
    {
        'title': _lazy('Home'), 'slug': '', 'template': SitePage.Template.HERO,
        'headline': _lazy('Welcome to {farm}'), 'subheading': _lazy('Fresh from our farm to you'),
        'cta_label': _lazy('Contact us'),
    },
    {
        'title': _lazy('About'), 'slug': 'about', 'template': SitePage.Template.ARTICLE,
        'headline': _lazy('Our story'),
    },
    {
        'title': _lazy('Our Record'), 'slug': 'verified', 'template': SitePage.Template.VERIFIED_STATS,
        'headline': _lazy('Our verified track record'),
    },
    {
        'title': _lazy('Contact'), 'slug': 'contact', 'template': SitePage.Template.CONTACT,
        'headline': _lazy('Get in touch'),
    },
]


def _get_or_create_site(farm):
    """Also backfills the starter pages onto any site that currently has
    none - not just a brand-new one - so a site created before this feature
    existed (or one where every page was since deleted) gets them on its
    owner's next visit too, instead of staying permanently blank."""
    site, _created = FarmSite.objects.get_or_create(farm=farm)
    if not site.pages.exists():
        SitePage.objects.bulk_create([
            SitePage(
                site=site, slug=p['slug'], template=p['template'],
                title=str(p['title']),
                headline=str(p['headline']).format(farm=farm.name) if 'headline' in p else '',
                subheading=str(p.get('subheading', '')),
                cta_label=str(p.get('cta_label', '')),
                order=i,
            )
            for i, p in enumerate(_STARTER_PAGES)
        ])
    return site


def _to_page_list(page=None):
    url = reverse('website:page_list')
    return redirect(f'{url}?page={page.id}' if page else url)


def _builder_shell(request, site, edit_form=None, editing_page=None, active_page=None):
    """Renders the one site-builder template (pages sidebar + live preview,
    see website/page_list.html) for all three of page_list/page_create/
    page_edit - editing happens at its own URL (/pages/add/, /pages/<id>/
    edit/) but always inside the same shell, never a separate full-page
    form, so the top bar and live preview stay on screen while a page's
    fields are being edited. Pages are always preloaded via `pages` below,
    whether or not edit_form is set."""
    pages = list(site.pages.all())
    if active_page is None:
        page_param = request.GET.get('page')
        if page_param:
            active_page = next((p for p in pages if str(p.id) == page_param), None)
        if active_page is None:
            active_page = next((p for p in pages if p.is_homepage), None)
    return render(request, 'website/page_list.html', {
        'site': site, 'pages': pages, 'active_page': active_page,
        'edit_form': edit_form, 'editing_page': editing_page,
    })


@manage_records_required
def site_settings(request):
    site = _get_or_create_site(request.farm)
    form = FarmSiteForm(request.POST or None, instance=site)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Website settings saved.'))
        return redirect('website:site_settings')
    return render(request, 'website/site_settings.html', {
        'site': site, 'form': form, 'theme_swatches': FarmSite.theme_swatches(),
    })


@manage_records_required
def page_list(request):
    site = _get_or_create_site(request.farm)
    return _builder_shell(request, site)


@manage_records_required
def page_create(request):
    site = _get_or_create_site(request.farm)
    form = SitePageForm(request.POST or None, request.FILES or None, site=site)
    if request.method == 'POST' and form.is_valid():
        page = form.save(commit=False)
        page.site = site
        page.save()
        messages.success(request, _('"%(title)s" added.') % {'title': page.title})
        return _to_page_list(page)
    return _builder_shell(request, site, edit_form=form)


@manage_records_required
def page_edit(request, page_id):
    site = _get_or_create_site(request.farm)
    page = get_object_or_404(SitePage, id=page_id, site=site)
    form = SitePageForm(request.POST or None, request.FILES or None, instance=page, site=site)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('"%(title)s" updated.') % {'title': page.title})
        return _to_page_list(page)
    return _builder_shell(request, site, edit_form=form, editing_page=page, active_page=page)


@manage_records_required
def page_delete(request, page_id):
    site = _get_or_create_site(request.farm)
    page = get_object_or_404(SitePage, id=page_id, site=site)
    if request.method == 'POST':
        title = page.title
        page.delete()
        messages.success(request, _('"%(title)s" deleted.') % {'title': title})
    return redirect('website:page_list')


# ------------------------------------------------------------ storefront (farm-scoped)

@manage_records_required
def product_list(request):
    products = Product.objects.filter(farm=request.farm).select_related('inventory_item')
    return render(request, 'website/product_list.html', {'products': products})


@manage_records_required
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.farm = request.farm
        product.save()
        notify(request.farm, request.user, Notification.Verb.CREATED, 'product', product.name)
        messages.success(request, _('%(name)s added to your storefront.') % {'name': product.name})
        return redirect('website:product_list')
    return render(request, 'website/product_form.html', {'form': form})


@manage_records_required
def product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id, farm=request.farm)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'product', product.name)
        messages.success(request, _('%(name)s updated.') % {'name': product.name})
        return redirect('website:product_list')
    return render(request, 'website/product_form.html', {'form': form, 'product': product})


@manage_records_required
def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id, farm=request.farm)
    if request.method == 'POST':
        name = product.name
        product.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'product', name)
        messages.success(request, _('%(name)s removed from your storefront.') % {'name': name})
    return redirect('website:product_list')


@any_member_required
def order_list(request):
    orders = Order.objects.filter(farm=request.farm).select_related('product')
    return render(request, 'website/order_list.html', {'orders': orders, 'status_choices': Order.Status.choices})


@edit_delete_required
def order_status_update(request, order_id):
    order = get_object_or_404(Order, id=order_id, farm=request.farm)
    new_status = request.POST.get('status')
    if request.method == 'POST' and new_status in Order.Status.values:
        order.status = new_status
        order.save(update_fields=['status'])
        messages.success(request, _('Order marked %(status)s.') % {'status': order.get_status_display().lower()})
    return redirect('website:order_list')


# ------------------------------------------------------------- public site


def _verified_stats(farm):
    """Only ever computed for a page the farm itself chose to publish with
    the "Verified farm stats" template - this is opt-in exposure of data
    that's otherwise farm-internal (see website.models.SitePage's
    docstring), not something shown automatically on every site."""
    from django.db.models import Sum
    from django.utils import timezone

    from blockchain.models import MilkProductionCertificate
    from cows.models import Cow
    from creditscore.models import CreditScoreSnapshot
    from crops.models import CropActivity

    certified_liters = MilkProductionCertificate.objects.filter(farm=farm).aggregate(
        total=Sum('total_liters')
    )['total'] or 0

    return {
        'active_cows': farm.cow_count,
        'verified_cows': Cow.objects.filter(farm=farm).exclude(hedera_token_id='').count(),
        'verified_harvests': CropActivity.objects.filter(farm=farm).exclude(hedera_token_id='').count(),
        'certified_liters': certified_liters,
        'years_active': max((timezone.now().date() - farm.created_at.date()).days // 365, 0),
        'latest_score': CreditScoreSnapshot.objects.filter(farm=farm).first(),
    }


def _render_site_page(request, site, page):
    context = {
        'site': site,
        'page': page,
        'nav_pages': site.pages.all(),
    }
    if page and page.template == SitePage.Template.VERIFIED_STATS:
        context['stats'] = _verified_stats(site.farm)
    if page and page.template == SitePage.Template.PRODUCTS:
        context['products'] = Product.objects.filter(farm=site.farm, is_available=True).select_related('inventory_item')
        context['order_form'] = OrderEnquiryForm()
    template_name = f'website/public/{page.template}.html' if page else 'website/public/empty.html'
    return render(request, template_name, context)


def _can_preview_unpublished(request, site):
    """Lets a farm's own owner/manager/supervisor open their site's public
    URL (and the builder's live-preview iframe, which loads that same URL)
    before it's published - anyone else still gets the normal 404 an
    unpublished site should give the public."""
    if not request.user.is_authenticated:
        return False
    from farms.models import FarmMembership
    return FarmMembership.objects.filter(farm=site.farm, user=request.user).exists()


@xframe_options_sameorigin
def public_home(request, slug):
    # Same-origin, not the project-wide default DENY (django.middleware
    # .clickjacking.XFrameOptionsMiddleware) - the builder's live preview
    # embeds this exact page in an <iframe> (see website/page_list.html),
    # which DENY silently blocks (a blank frame, no console error visible
    # to a casual look).
    site = get_object_or_404(FarmSite, slug=slug)
    if not site.is_published and not _can_preview_unpublished(request, site):
        raise Http404
    page = site.pages.filter(slug='').first()
    return _render_site_page(request, site, page)


@xframe_options_sameorigin
def public_page(request, slug, page_slug):
    site = get_object_or_404(FarmSite, slug=slug)
    if not site.is_published and not _can_preview_unpublished(request, site):
        raise Http404
    page = get_object_or_404(SitePage, site=site, slug=page_slug)
    return _render_site_page(request, site, page)


@require_POST
def order_create(request, slug):
    """Public, unauthenticated - a visitor on the farm's PRODUCTS page
    submitting an enquiry/order. No payment is taken here (see Order's
    docstring); the farmer follows up and arranges it themselves. The
    `website` field is a honeypot (see OrderEnquiryForm) - a bot that fills
    it in gets a normal-looking redirect back with no Order ever created."""
    site = get_object_or_404(FarmSite, slug=slug)
    if not site.is_published:
        raise Http404
    product = get_object_or_404(Product, id=request.POST.get('product_id'), farm=site.farm, is_available=True)

    form = OrderEnquiryForm(request.POST)
    if form.is_valid():
        if form.cleaned_data['website']:
            return redirect('website_public:page', slug=slug, page_slug=request.POST.get('page_slug', ''))
        order = form.save(commit=False)
        order.farm = site.farm
        order.product = product
        order.save()
        from farms.models import FarmMembership, FarmRole

        recipients = FarmMembership.objects.filter(
            farm=site.farm, status=FarmMembership.Status.ACTIVE, role__in=[FarmRole.FARMER, FarmRole.MANAGER]
        ).select_related('user')
        for membership in recipients:
            notify(
                site.farm, None, Notification.Verb.CREATED, 'order',
                f'{order.buyer_name} wants {order.quantity} {product.unit} of {product.name}',
                recipient=membership.user,
            )
        messages.success(request, _("Thanks! %(name)s will be in touch with you shortly.") % {'name': site.farm.name})
    page_slug = request.POST.get('page_slug', '')
    if page_slug:
        return redirect('website_public:page', slug=slug, page_slug=page_slug)
    return redirect('website_public:home', slug=slug)
