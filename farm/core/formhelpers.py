from django import forms

INPUT_CLASSES = (
    'w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm '
    'text-stone-900 placeholder-stone-400 focus:border-emerald-600 '
    'focus:ring-2 focus:ring-emerald-100 focus:outline-none transition'
)
SELECT_CLASSES = INPUT_CLASSES
CHECKBOX_CLASSES = 'h-4 w-4 rounded border-stone-300 text-emerald-600 focus:ring-emerald-500'
OTP_INPUT_CLASSES = (
    'w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-center '
    'text-2xl tracking-[0.6em] font-semibold text-stone-900 '
    'focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100 focus:outline-none transition'
)


class TailwindFormMixin:
    """Applies consistent Tailwind classes to every field automatically so
    individual forms don't need to repeat widget attrs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', CHECKBOX_CLASSES)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', SELECT_CLASSES)
            else:
                widget.attrs.setdefault('class', INPUT_CLASSES)
            widget.attrs.setdefault('autocomplete', 'off')
