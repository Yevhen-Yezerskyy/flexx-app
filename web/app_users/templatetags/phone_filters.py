from __future__ import annotations

from django import template

from flexx.phone_utils import format_phone_international

register = template.Library()


@register.filter(name="phone_intl")
def phone_intl(value):
    return format_phone_international(value)
