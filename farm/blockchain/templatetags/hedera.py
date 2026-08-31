from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def hedera_token_url(token_id, serial=None):
    if not token_id:
        return ''
    base = f'https://hashscan.io/{settings.HEDERA_NETWORK}/token/{token_id}'
    return f'{base}/{serial}' if serial else base


@register.simple_tag
def hedera_topic_url(topic_id):
    if not topic_id:
        return ''
    return f'https://hashscan.io/{settings.HEDERA_NETWORK}/topic/{topic_id}'


@register.simple_tag
def hedera_transaction_url(transaction_id):
    if not transaction_id:
        return ''
    return f'https://hashscan.io/{settings.HEDERA_NETWORK}/transaction/{transaction_id}'
