from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from blockchain.models import FiqLedgerEntry
from cows.models import Cow
from farms.models import Block, Farm, FarmMembership, FarmRole
from inventory.models import InventoryItem
from notifications.models import Notification

from .models import FarmSite, Order, Product, SitePage, generate_site_slug


def _farm_with_owner(name):
    user = User.objects.create_user(email=f'{name.lower().replace(" ", "_")}@example.com', first_name='Test')
    farm = Farm.objects.create(name=name, owner=user)
    FarmMembership.objects.create(farm=farm, user=user, role=FarmRole.FARMER)
    return farm, user


class SlugGenerationTests(TestCase):
    def test_slug_is_derived_from_farm_name(self):
        self.assertEqual(generate_site_slug('Green Valley Farm'), 'green-valley-farm')

    def test_slug_collision_appends_a_counter(self):
        farm1, _owner = _farm_with_owner('Slug Collision Farm 1')
        FarmSite.objects.create(farm=farm1, slug='green-valley')
        self.assertEqual(generate_site_slug('green-valley'), 'green-valley-2')

    def test_blank_slug_auto_generates_on_save(self):
        farm, _user = _farm_with_owner('Auto Slug Farm')
        site = FarmSite.objects.create(farm=farm)
        self.assertEqual(site.slug, 'auto-slug-farm')

    def test_reserved_word_slug_gets_a_counter_instead(self):
        # A farm literally named "Website" would otherwise generate the same
        # slug as the /website/ app prefix, making its own site unreachable
        # at its own address (shadowed by the real app - see
        # website.models.RESERVED_SLUGS).
        self.assertEqual(generate_site_slug('Website'), 'website-2')


class HomepageUniquenessTests(TestCase):
    def test_only_one_page_can_hold_the_blank_homepage_slug(self):
        farm, _user = _farm_with_owner('Homepage Farm')
        site = FarmSite.objects.create(farm=farm)
        SitePage.objects.create(site=site, title='Home', slug='', template=SitePage.Template.HERO)
        with self.assertRaises(Exception):
            SitePage.objects.create(site=site, title='Another Home', slug='', template=SitePage.Template.ARTICLE)


class PublicSiteRenderingTests(TestCase):
    def setUp(self):
        self.farm, self.owner = _farm_with_owner('Public Site Farm')
        self.site = FarmSite.objects.create(farm=self.farm, is_published=True)

    def test_unpublished_site_404s(self):
        self.site.is_published = False
        self.site.save(update_fields=['is_published'])
        resp = self.client.get(reverse('website_public:home', args=[self.site.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_published_site_with_no_homepage_shows_placeholder(self):
        resp = self.client.get(reverse('website_public:home', args=[self.site.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'still being built', resp.content)

    def test_published_hero_homepage_renders(self):
        SitePage.objects.create(
            site=self.site, title='Home', slug='', template=SitePage.Template.HERO,
            headline='Welcome to our farm', cta_label='Get in touch', cta_url='https://example.com',
        )
        resp = self.client.get(reverse('website_public:home', args=[self.site.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Welcome to our farm', resp.content)
        self.assertIn(b'Get in touch', resp.content)

    def test_named_subpage_renders_at_its_own_url(self):
        SitePage.objects.create(site=self.site, title='About', slug='about', template=SitePage.Template.ARTICLE, body='Our story.')
        resp = self.client.get(reverse('website_public:page', args=[self.site.slug, 'about']))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Our story.', resp.content)

    def test_unknown_farm_slug_404s(self):
        resp = self.client.get(reverse('website_public:home', args=['no-such-farm']))
        self.assertEqual(resp.status_code, 404)


class DraftPreviewTests(TestCase):
    """An unpublished site still 404s to the public, but its own farm can
    preview it - see website.views._can_preview_unpublished."""

    def setUp(self):
        self.farm, self.owner = _farm_with_owner('Draft Preview Farm')
        self.site = FarmSite.objects.create(farm=self.farm, is_published=False)
        SitePage.objects.create(site=self.site, title='Home', slug='', template=SitePage.Template.HERO, headline='Draft headline')
        _outsider_farm, self.outsider = _farm_with_owner('Outsider Farm')

    def test_anonymous_visitor_gets_404_on_unpublished_site(self):
        resp = self.client.get(reverse('website_public:home', args=[self.site.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_unrelated_logged_in_user_gets_404_on_unpublished_site(self):
        self.client.force_login(self.outsider)
        resp = self.client.get(reverse('website_public:home', args=[self.site.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_farm_owner_can_preview_their_own_unpublished_site(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('website_public:home', args=[self.site.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Draft headline', resp.content)
        self.assertIn(b'Draft preview', resp.content)


class VerifiedStatsTests(TestCase):
    def test_verified_stats_page_shows_real_on_chain_counts(self):
        farm, _owner = _farm_with_owner('Verified Stats Farm')
        site = FarmSite.objects.create(farm=farm, is_published=True)
        SitePage.objects.create(site=site, title='Verified', slug='', template=SitePage.Template.VERIFIED_STATS)

        block = Block.objects.create(farm=farm, name='Block A')
        Cow.objects.create(farm=farm, tag_id='V-1', breed='Friesian', status=Cow.Status.ACTIVE, block=block, hedera_token_id='0.0.999')
        Cow.objects.create(farm=farm, tag_id='V-2', breed='Friesian', status=Cow.Status.ACTIVE, block=block)  # not verified
        FiqLedgerEntry.objects.create(farm=farm, amount=Decimal('10'), reason=FiqLedgerEntry.Reason.COW_REGISTERED)

        resp = self.client.get(reverse('website_public:home', args=[site.slug]))
        content = resp.content.decode()
        self.assertEqual(resp.status_code, 200)
        # 2 active cows total, only 1 verified on-chain
        self.assertIn('>2<', content)
        self.assertIn('>1<', content)


class CMSPermissionTests(TestCase):
    def setUp(self):
        self.farm, self.owner = _farm_with_owner('CMS Permission Farm')
        self.worker = User.objects.create_user(email='cms_worker@example.com', first_name='Worker')
        FarmMembership.objects.create(farm=self.farm, user=self.worker, role=FarmRole.WORKER)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_worker_cannot_reach_site_settings(self):
        self._login(self.worker)
        resp = self.client.get(reverse('website:site_settings'))
        self.assertNotEqual(resp.status_code, 200)

    def test_owner_can_reach_site_settings_and_it_creates_the_site(self):
        self._login(self.owner)
        self.assertFalse(FarmSite.objects.filter(farm=self.farm).exists())
        resp = self.client.get(reverse('website:site_settings'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(FarmSite.objects.filter(farm=self.farm).exists())

    def test_new_site_comes_preloaded_with_starter_pages(self):
        self._login(self.owner)
        self.client.get(reverse('website:site_settings'))  # first-ever visit creates the site
        site = FarmSite.objects.get(farm=self.farm)
        self.assertEqual(site.pages.count(), 4)
        self.assertTrue(site.pages.filter(slug='').exists())  # one of them is the homepage

    def test_an_existing_but_emptied_site_gets_starter_pages_back(self):
        # A site created before the starter-pages feature existed (or one a
        # farmer emptied out entirely) should still get a real starting
        # point on its next visit, not stay permanently blank.
        self._login(self.owner)
        site = FarmSite.objects.create(farm=self.farm)  # simulates a pre-existing, page-less site
        self.assertEqual(site.pages.count(), 0)
        self.client.get(reverse('website:site_settings'))
        self.assertEqual(site.pages.count(), 4)

    def test_owner_can_create_and_publish_a_page(self):
        self._login(self.owner)
        self.client.get(reverse('website:site_settings'))  # ensures the site (and its starter pages) exist
        starter_count = SitePage.objects.filter(site__farm=self.farm).count()
        resp = self.client.post(reverse('website:page_create'), {
            'title': 'Gallery', 'slug': 'gallery', 'template': SitePage.Template.ARTICLE,
            'headline': 'Hello', 'subheading': '', 'body': '', 'image_url': '',
            'cta_label': '', 'cta_url': '', 'contact_phone': '', 'contact_email': '', 'order': 0,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SitePage.objects.filter(site__farm=self.farm).count(), starter_count + 1)


class ProductPermissionTests(TestCase):
    def setUp(self):
        self.farm, self.owner = _farm_with_owner('Storefront Farm')
        self.worker = User.objects.create_user(email='storefront_worker@example.com', first_name='Worker')
        FarmMembership.objects.create(farm=self.farm, user=self.worker, role=FarmRole.WORKER)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_worker_cannot_create_a_product(self):
        self._login(self.worker)
        self.client.post(reverse('website:product_create'), {
            'name': 'Fresh milk', 'inventory_item': '', 'description': '', 'price': '80.00',
            'unit': 'per liter', 'is_available': 'on',
        })
        self.assertFalse(Product.objects.filter(farm=self.farm).exists())

    def test_owner_can_create_a_product(self):
        self._login(self.owner)
        self.client.post(reverse('website:product_create'), {
            'name': 'Fresh milk', 'inventory_item': '', 'description': '', 'price': '80.00',
            'unit': 'per liter', 'is_available': 'on',
        })
        self.assertTrue(Product.objects.filter(farm=self.farm, name='Fresh milk').exists())

    def test_inventory_item_choices_scoped_to_farm_produce(self):
        other_farm, _other_owner = _farm_with_owner('Other Storefront Farm')
        own_milk = InventoryItem.objects.create(farm=self.farm, name='Milk', category=InventoryItem.Category.PRODUCE)
        InventoryItem.objects.create(farm=self.farm, name='Dairy Meal', category=InventoryItem.Category.FEED)
        InventoryItem.objects.create(farm=other_farm, name='Milk', category=InventoryItem.Category.PRODUCE)
        self._login(self.owner)
        resp = self.client.get(reverse('website:product_create'))
        choices = list(resp.context['form'].fields['inventory_item'].queryset)
        self.assertEqual(choices, [own_milk])


class OrderCreateViewTests(TestCase):
    def setUp(self):
        self.farm, self.owner = _farm_with_owner('Order Farm')
        self.manager = User.objects.create_user(email='order_manager@example.com', first_name='Manager')
        FarmMembership.objects.create(farm=self.farm, user=self.manager, role=FarmRole.MANAGER)
        self.site = FarmSite.objects.create(farm=self.farm, is_published=True)
        self.page = SitePage.objects.create(site=self.site, title='Shop', slug='shop', template=SitePage.Template.PRODUCTS)
        self.product = Product.objects.create(farm=self.farm, name='Fresh milk', price=Decimal('80.00'), unit='per liter')

    def _order_url(self):
        return reverse('website_public:order_create', args=[self.site.slug])

    def test_valid_submission_creates_an_order_and_notifies_managers(self):
        resp = self.client.post(self._order_url(), {
            'product_id': self.product.id, 'page_slug': self.page.slug, 'website': '',
            'quantity': '5', 'buyer_name': 'Jane Buyer', 'buyer_phone': '+254700000000', 'buyer_note': '',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        order = Order.objects.get(farm=self.farm)
        self.assertEqual(order.buyer_name, 'Jane Buyer')
        self.assertEqual(order.product, self.product)
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertTrue(Notification.objects.filter(farm=self.farm, kind='order', recipient=self.manager).exists())

    def test_honeypot_filled_in_silently_drops_the_order(self):
        resp = self.client.post(self._order_url(), {
            'product_id': self.product.id, 'page_slug': self.page.slug, 'website': 'http://spam.example.com',
            'quantity': '5', 'buyer_name': 'Bot', 'buyer_phone': '000', 'buyer_note': '',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Order.objects.filter(farm=self.farm).exists())

    def test_unavailable_product_cannot_be_ordered(self):
        self.product.is_available = False
        self.product.save(update_fields=['is_available'])
        resp = self.client.post(self._order_url(), {
            'product_id': self.product.id, 'page_slug': self.page.slug, 'website': '',
            'quantity': '5', 'buyer_name': 'Jane Buyer', 'buyer_phone': '+254700000000', 'buyer_note': '',
        })
        self.assertEqual(resp.status_code, 404)

    def test_order_for_another_farms_product_404s(self):
        other_farm, _other_owner = _farm_with_owner('Other Order Farm')
        other_product = Product.objects.create(farm=other_farm, name='Eggs', price=Decimal('10.00'), unit='per dozen')
        resp = self.client.post(self._order_url(), {
            'product_id': other_product.id, 'page_slug': self.page.slug, 'website': '',
            'quantity': '1', 'buyer_name': 'Jane Buyer', 'buyer_phone': '+254700000000', 'buyer_note': '',
        })
        self.assertEqual(resp.status_code, 404)

    def test_unpublished_site_cannot_receive_orders(self):
        self.site.is_published = False
        self.site.save(update_fields=['is_published'])
        resp = self.client.post(self._order_url(), {
            'product_id': self.product.id, 'page_slug': self.page.slug, 'website': '',
            'quantity': '5', 'buyer_name': 'Jane Buyer', 'buyer_phone': '+254700000000', 'buyer_note': '',
        })
        self.assertEqual(resp.status_code, 404)

    def test_products_page_lists_only_available_products(self):
        Product.objects.create(farm=self.farm, name='Hidden item', price=Decimal('5.00'), unit='each', is_available=False)
        resp = self.client.get(reverse('website_public:page', args=[self.site.slug, self.page.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['products']), [self.product])


class OrderListPermissionTests(TestCase):
    def setUp(self):
        self.farm, self.owner = _farm_with_owner('Order List Farm')
        self.worker = User.objects.create_user(email='orderlist_worker@example.com', first_name='Worker')
        FarmMembership.objects.create(farm=self.farm, user=self.worker, role=FarmRole.WORKER)
        self.product = Product.objects.create(farm=self.farm, name='Fresh milk', price=Decimal('80.00'), unit='per liter')
        self.order = Order.objects.create(
            farm=self.farm, product=self.product, quantity=Decimal('5'),
            buyer_name='Jane', buyer_phone='+254700000000',
        )

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_any_member_can_view_orders(self):
        self._login(self.worker)
        resp = self.client.get(reverse('website:order_list'))
        self.assertEqual(resp.status_code, 200)

    def test_worker_cannot_update_order_status(self):
        self._login(self.worker)
        self.client.post(reverse('website:order_status_update', args=[self.order.id]), {'status': Order.Status.FULFILLED})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)

    def test_owner_can_update_order_status(self):
        self._login(self.owner)
        self.client.post(reverse('website:order_status_update', args=[self.order.id]), {'status': Order.Status.FULFILLED})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.FULFILLED)
