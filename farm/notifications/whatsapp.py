import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_whatsapp_message(phone_number, text):
    """Send a plain-text WhatsApp message via Meta's Cloud API. Best-effort,
    same contract as notifications.push.send_push_to_user: never raises, so
    a WhatsApp delivery failure (or WhatsApp simply not being configured
    yet - see settings.WHATSAPP_ACCESS_TOKEN) never blocks the request that
    triggered the notification.

    Only works as a free-form message within a 24h window of the recipient
    having messaged the business's WhatsApp number - outside that, Meta
    requires a pre-approved message template instead, which is a Meta
    Business account setup concern, not something this function can work
    around."""
    if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID and phone_number):
        return
    url = (
        f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}'
        f'/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages'
    )
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'text',
        'text': {'body': text[:4096]},
    }
    headers = {'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}'}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if not response.ok:
            logger.warning('WhatsApp send failed for %s (status %s): %s', phone_number, response.status_code, response.text)
    except requests.RequestException:
        logger.exception('Unexpected error sending WhatsApp message to %s', phone_number)
