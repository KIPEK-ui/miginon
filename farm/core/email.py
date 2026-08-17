import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

_BLOCK_BREAK_RE = re.compile(r'(?i)</(p|div|tr|h[1-6]|table)>')
_LINE_BREAK_RE = re.compile(r'(?i)<br\s*/?>')
_BLANK_RUN_RE = re.compile(r'\n{3,}')
_SPACE_RUN_RE = re.compile(r'[ \t]+')


def _html_to_text(html):
    """A readable plain-text fallback for an HTML email. Plain strip_tags()
    on a table-based layout collapses every cell into one run-on line, so
    this inserts line breaks at the block-level tags first."""
    text = _LINE_BREAK_RE.sub('\n', html)
    text = _BLOCK_BREAK_RE.sub('\n', text)
    text = strip_tags(text)
    text = _SPACE_RUN_RE.sub(' ', text)
    text = _BLANK_RUN_RE.sub('\n\n', text)
    return text.strip()


def send_styled_email(to, subject, template_name, context=None, attachments=None):
    """Render `template_name` (an emails/*.html template extending
    emails/base_email.html) to HTML, derive a plain-text fallback from it,
    and send both via the configured EMAIL_BACKEND.

    `attachments` is an optional list of (filename, content_bytes, mimetype)
    tuples, e.g. for attaching a generated PDF report.
    """
    context = {**(context or {}), 'current_year': timezone.now().year}
    html_body = render_to_string(template_name, context)
    text_body = _html_to_text(html_body)

    recipients = [to] if isinstance(to, str) else list(to)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    message.attach_alternative(html_body, 'text/html')
    for filename, content, mimetype in attachments or []:
        message.attach(filename, content, mimetype)
    message.send()


def send_styled_email_safely(*args, **kwargs):
    """Same as send_styled_email, but for non-critical emails (welcome,
    milestone, worker-added) where a delivery failure shouldn't break the
    request that triggered it - e.g. signup should still succeed even if
    Zoho is unreachable. OTP emails intentionally do NOT use this: the user
    needs that email to proceed, so a failure there should surface loudly.
    """
    try:
        send_styled_email(*args, **kwargs)
    except Exception:
        logger.exception('Non-critical email failed to send (subject=%r)', kwargs.get('subject', args[1] if len(args) > 1 else ''))
