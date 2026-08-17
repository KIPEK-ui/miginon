from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from core.email import send_styled_email


class Command(BaseCommand):
    help = 'Send a newsletter-style email to every active user with a verified email address.'

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Email subject line.')
        parser.add_argument('--heading', required=True, help='Heading shown at the top of the email body.')
        parser.add_argument(
            '--body', required=True,
            help='Body text. Separate paragraphs with a blank line (double newline).',
        )
        parser.add_argument('--cta-text', default='', help='Optional call-to-action button label.')
        parser.add_argument('--cta-url', default='', help='Optional call-to-action button URL.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List recipients and render the email without sending anything.',
        )

    def handle(self, *args, **options):
        cta_text = options['cta_text']
        cta_url = options['cta_url']
        if bool(cta_text) != bool(cta_url):
            raise CommandError('--cta-text and --cta-url must be provided together.')

        paragraphs = [p.strip() for p in options['body'].split('\n\n') if p.strip()]
        if not paragraphs:
            raise CommandError('--body must contain at least one paragraph.')

        recipients = list(User.objects.filter(is_active=True).exclude(email='').order_by('email'))
        if not recipients:
            self.stdout.write(self.style.WARNING('No active users with an email address found.'))
            return

        if options['dry_run']:
            self.stdout.write(f'Would email {len(recipients)} user(s):')
            for user in recipients:
                self.stdout.write(f'  - {user.email}')
            return

        sent, failed = 0, 0
        for user in recipients:
            context = {'user': user, 'heading': options['heading'], 'paragraphs': paragraphs}
            if cta_text and cta_url:
                context['cta_text'] = cta_text
                context['cta_url'] = cta_url
            try:
                send_styled_email(
                    to=user.email,
                    subject=options['subject'],
                    template_name='emails/newsletter.html',
                    context=context,
                )
                sent += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f'Failed to email {user.email}: {exc}'))

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} newsletter email(s), {failed} failed.'))
