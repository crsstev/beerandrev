from django.core.management.base import BaseCommand
from tracker.models import GameStatistic
from tracker.steam import fetch_steam_app_id


class Command(BaseCommand):
    help = 'Fetch Steam app IDs for all games missing them'

    def handle(self, *args, **options):
        games = GameStatistic.objects.filter(steam_app_id__isnull=True)
        self.stdout.write(f"Found {games.count()} games without Steam IDs")

        for stat in games:
            app_id = fetch_steam_app_id(stat.game_name)
            if app_id:
                stat.steam_app_id = app_id
                stat.save(update_fields=['steam_app_id'])
                self.stdout.write(f"  {stat.game_name} -> {app_id}")
            else:
                self.stdout.write(f"  {stat.game_name} -> not found")

        self.stdout.write(self.style.SUCCESS('Done'))
