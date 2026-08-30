def theme(request):
    """Effective light/dark theme for this request - the signed-in user's
    saved preference, or the `theme` cookie for anonymous visitors (landing,
    login, signup) so the toggle still works before there's a User row to
    save it on."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        pref = user.theme_preference
    else:
        pref = request.COOKIES.get('theme', 'light')
    return {'theme': pref if pref in ('light', 'dark') else 'light'}
