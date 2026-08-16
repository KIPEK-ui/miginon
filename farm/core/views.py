from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect('farms:dashboard')
    features = [
        ('water-outline', 'Milk production', 'Log AM, noon and PM milk yields per block and track trends over time.'),
        ('nutrition-outline', 'Feeding records', 'Record dairy meal and silage/hay per block and session, just like your feeding chart.'),
        ('paw-outline', 'Herd tracking', 'Organize cows into blocks/paddocks with tags, breed and status.'),
        ('lock-closed-outline', 'Email OTP login', 'No passwords. Sign in with your Farm ID, email, and a 6-digit code.'),
    ]
    return render(request, 'core/landing.html', {'features': features})
