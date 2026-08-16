from django.conf import settings
from django.core.mail import send_mail


def send_worker_added_email(membership):
    farm = membership.farm
    message = (
        f'You have been added to {farm.name} on Miginon Farm as a '
        f'{membership.get_role_display()}.\n\n'
        f'To sign in, go to the login page and enter:\n'
        f'  Farm ID: {farm.code}\n'
        f'  Email:   {membership.user.email}\n\n'
        f"You'll receive a one-time code by email each time you sign in - no password needed."
    )
    send_mail(
        subject=f'You were added to {farm.name} on Miginon Farm',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[membership.user.email],
    )
