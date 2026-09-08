from django import template
register = template.Library()


@register.filter
def money(value):
    try:
        return f"€{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def compact_money(value):
    try:
        value = float(value)
        if abs(value) >= 1_000_000:
            return f"€{value / 1_000_000:,.2f}m"
        if abs(value) >= 1000:
            return f"€{value / 1000:,.1f}k"
        return money(value)
    except (TypeError, ValueError):
        return "—"


@register.filter
def number(value):
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def pct(value):
    return f"{float(value) * 100:,.0f}%"


@register.filter
def precise_pct(value):
    percent = float(value) * 100
    return "<0.01%" if 0 < percent < .01 else f"{percent:,.2f}".rstrip("0").rstrip(".") + "%"


@register.filter
def getitem(value, key):
    return value.get(key)


@register.filter
def plus(value, other):
    return float(value) + float(other)
