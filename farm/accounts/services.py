from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailOTP


def issue_otp(email, purpose, farm=None):
    """Invalidate any previous unused OTPs for this email/purpose/farm and
    issue + send a fresh one."""
    EmailOTP.objects.filter(
        email=email, purpose=purpose, farm=farm, is_used=False
    ).update(is_used=True)

    otp = EmailOTP.objects.create(email=email, purpose=purpose, farm=farm)
    send_otp_email(otp)
    return otp


def send_otp_email(otp: EmailOTP):
    if otp.purpose == EmailOTP.Purpose.SIGNUP:
        subject = 'Verify your email - Miginon Farm'
        intro = 'Welcome to Miginon Farm! Use the code below to verify your email and finish setting up your farm.'
    elif otp.purpose == EmailOTP.Purpose.EMAIL_CHANGE:
        subject = 'Confirm your new email - Miginon Farm'
        intro = 'Use the code below to confirm this is your new email address.'
    else:
        farm_bit = f' for {otp.farm.name}' if otp.farm else ''
        subject = 'Your Miginon Farm login code'
        intro = f'Use the code below to sign in{farm_bit}.'

    message = (
        f'{intro}\n\n'
        f'    {otp.code}\n\n'
        f'This code expires in {settings.OTP_VALIDITY_MINUTES} minutes. '
        f'If you did not request this, you can safely ignore this email.'
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[otp.email],
    )


def can_resend(last_otp):
    if not last_otp:
        return True
    elapsed = (timezone.now() - last_otp.created_at).total_seconds()
    return elapsed >= settings.OTP_RESEND_COOLDOWN_SECONDS
