import math
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from usage_api import store


class Command(BaseCommand):
    help = "Add varied sample usage with dense recent activity and a year of history."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1000)
        parser.add_argument("--days", type=float, default=365)

    def handle(self, *args, **options):
        count = options["count"]
        days = options["days"]
        if count < 1 or not 0 < days <= 36500:
            raise CommandError("--count must be positive; --days must be between 0 and 36500")
        generator = random.Random(42)
        now = timezone.now()
        horizon = timedelta(days=days)
        gaps = [
            (timedelta(days=start), timedelta(days=end))
            for start, end in ((3, 4), (30, 35))
            if timedelta(days=end) <= horizon
        ]

        def in_gap(offset):
            return any(start < offset < end for start, end in gaps)

        # Include limits, tiny decimals, identical timestamps, and a sharp spike.
        samples = [
            (timedelta(0), 0.0),
            (horizon, 100.0),
            (timedelta(seconds=1), 100.0),
            (timedelta(minutes=1), 0.01),
            (timedelta(minutes=1), 0.01),
            (timedelta(minutes=5), 99.99),
            (timedelta(minutes=10), 100.0),
            (timedelta(minutes=11), 2.0),
        ]
        # Samples just inside, on, and outside each preset boundary.
        for minutes in (15, 30, 60, 180, 720, 1440, 10080):
            for seconds in (-1, 0, 1):
                samples.append((timedelta(minutes=minutes, seconds=seconds), 25.0 + seconds))
        samples.extend((timedelta(minutes=minute), 50.0) for minute in range(45, 56, 2))
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for boundary in (midnight, midnight.replace(day=1)):
            for seconds in (-1, 0, 1):
                samples.append((now - boundary + timedelta(seconds=seconds), 20.0 + seconds))
        samples = [
            (offset, usage) for offset, usage in samples
            if timedelta(0) <= offset <= horizon and not in_gap(offset)
        ][:count]

        while len(samples) < count:
            # Bias toward recent activity while retaining older, sparse history.
            offset = horizon * generator.random() ** 4
            if in_gap(offset):
                continue
            minutes = offset.total_seconds() / 60
            if 45 <= minutes <= 55:
                usage = 50.0
            elif generator.random() < 0.08:
                usage = generator.choice((0.0, 100.0))
            else:
                baseline = 45 + 30 * math.sin(minutes * math.tau / 30)
                usage = round(max(0, min(100, baseline + generator.uniform(-12, 12))), 2)
            samples.append((offset, usage))

        records = [
            {"usage": usage, "timestamp": store.utc_timestamp(now - offset)}
            for offset, usage in samples
        ]
        store.add_records(records)
        self.stdout.write(self.style.SUCCESS(f"Added {count} sample usage records across {days:g} days."))
