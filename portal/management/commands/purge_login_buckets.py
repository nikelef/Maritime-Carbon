from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from portal.models import LoginBucket


class Command(BaseCommand):
    help = "Delete expired login-rate-limit buckets older than one day."

    def handle(self, **options):
        count, _ = LoginBucket.objects.filter(started_at__lt=timezone.now() - timedelta(days=1)).delete()
        self.stdout.write(f"Removed {count} expired throttle buckets.")
