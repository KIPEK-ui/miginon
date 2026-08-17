from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect('farms:dashboard')

    features = [
        ('water-outline', 'Milk production', 'Log AM, noon and PM yields per cow and block, and watch weekly and monthly trends on the dashboard.'),
        ('nutrition-outline', 'Feeding records', 'Record dairy meal and silage/hay per block and session, just like your existing feeding chart.'),
        ('paw-outline', 'Herd management', 'Organize cows, heifers, calves and bulls into blocks with tags, breed, gender and status - transfer between blocks in a click.'),
        ('leaf-outline', 'Crop tracking', 'Track every crop from planting to harvest, and log weeding, spraying, fertilizing and harvest activity per field.'),
        ('cube-outline', 'Inventory & stock', 'Track feed, veterinary supplies and equipment stock, with automatic low-stock warnings before you run out.'),
        ('cash-outline', 'Finance', 'Record income and expenses by category and see your real-time net position for the farm.'),
        ('bar-chart-outline', 'Reports & analytics', 'A full dashboard plus one-click exports to CSV, Excel or PDF - or have a report emailed to you instantly.'),
        ('notifications-outline', 'Activity feed', 'Every teammate sees who added, changed or removed what, in real time, right on their dashboard.'),
        ('lock-closed-outline', 'Passwordless login', 'No passwords to remember or leak. Sign in with your Farm ID, email and a 6-digit one-time code.'),
        ('people-outline', 'Role-based access', 'Farmer, Manager, Supervisor and Worker - everyone sees exactly the tools their role needs, nothing more.'),
        ('business-outline', 'Multi-farm support', 'Run more than one farm from a single account, each with its own team, herd and records.'),
        ('phone-portrait-outline', 'Install as an app', 'Add Miginon Farm to your home screen and use it full-screen, offline-friendly, like a native app.'),
    ]

    steps = [
        ('1', 'Create your farm', 'Sign up in under a minute and get a unique Farm ID instantly - that ID is how your whole team signs in.'),
        ('2', 'Set up blocks & herd', 'Add your blocks or paddocks, then register your cows, heifers, calves and bulls against them.'),
        ('3', 'Invite your team', 'Add managers, supervisors and workers by email. No passwords to hand out - just OTP codes.'),
        ('4', 'Log daily & review', 'Record milk, feeding, crops, inventory and finance as you go, then check the dashboard or export a report.'),
    ]

    return render(request, 'core/landing.html', {'features': features, 'steps': steps})
