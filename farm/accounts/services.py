import logging

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from core.email import send_styled_email

from .models import EmailOTP

logger = logging.getLogger(__name__)


class OTPDeliveryError(Exception):
    """The OTP row was created but the email could not be sent (e.g. the
    SMTP provider rejected or throttled it). Callers should catch this and
    show the user a friendly retry message instead of a raw 500."""


def issue_otp(email, purpose, farm=None):
    """Invalidate any previous unused OTPs for this email/purpose/farm and
    issue + send a fresh one.

    Guarded by the same resend cooldown as the explicit "resend" views: a
    double form submission (double-click, slow SMTP round-trip prompting an
    impatient resubmit, browser retry) would otherwise create and email two
    different codes a few hundred milliseconds apart. If a still-valid,
    unused OTP for this email/purpose/farm was already issued within the
    cooldown window, reuse it instead of sending a second email.
    """
    last_otp = (
        EmailOTP.objects.filter(email=email, purpose=purpose, farm=farm)
        .order_by('-created_at')
        .first()
    )
    if last_otp and not last_otp.is_used and last_otp.is_valid() and not can_resend(last_otp):
        return last_otp

    EmailOTP.objects.filter(
        email=email, purpose=purpose, farm=farm, is_used=False
    ).update(is_used=True)

    otp = EmailOTP.objects.create(email=email, purpose=purpose, farm=farm)
    try:
        send_otp_email(otp)
    except Exception as exc:
        logger.exception('Failed to send OTP email to %s (purpose=%s)', email, purpose)
        raise OTPDeliveryError('Could not send the verification code email.') from exc
    return otp


def send_otp_email(otp: EmailOTP):
    if otp.purpose == EmailOTP.Purpose.SIGNUP:
        subject = _('Verify your email - FarmIQ')
        heading = _('Verify your email')
        intro = _('Welcome to FarmIQ! Use the code below to verify your email and finish setting up your farm.')
    elif otp.purpose == EmailOTP.Purpose.EMAIL_CHANGE:
        subject = _('Confirm your new email - FarmIQ')
        heading = _('Confirm your new email')
        intro = _('Use the code below to confirm this is your new email address.')
    else:
        farm_bit = _(' for %(farm)s') % {'farm': otp.farm.name} if otp.farm else ''
        subject = _('Your FarmIQ login code')
        heading = _('Your login code')
        intro = _('Use the code below to sign in%(farm_bit)s.') % {'farm_bit': farm_bit}

    # OTP delivery is on the critical path (the user can't proceed without
    # it), so unlike the "nice to have" emails this is left to raise if
    # sending fails, rather than being swallowed by send_styled_email_safely.
    send_styled_email(
        to=otp.email,
        subject=subject,
        template_name='emails/otp_code.html',
        context={
            'heading': heading,
            'intro': intro,
            'code': otp.code,
            'validity_minutes': settings.OTP_VALIDITY_MINUTES,
        },
    )


def can_resend(last_otp):
    if not last_otp:
        return True
    elapsed = (timezone.now() - last_otp.created_at).total_seconds()
    return elapsed >= settings.OTP_RESEND_COOLDOWN_SECONDS
