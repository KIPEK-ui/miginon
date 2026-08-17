from django.urls import reverse

from core.email import send_styled_email_safely


def send_worker_added_email(membership, request):
    farm = membership.farm
    send_styled_email_safely(
        to=membership.user.email,
        subject=f'You were added to {farm.name} on Farm IQ',
        template_name='emails/worker_added.html',
        context={
            'membership': membership, 'farm': farm,
            'login_url': request.build_absolute_uri(reverse('accounts:login_farm')),
        },
    )
