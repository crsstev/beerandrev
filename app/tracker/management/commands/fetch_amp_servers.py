import os
import requests
import urllib.request
from pathlib import Path
from django.core.management.base import BaseCommand
from tracker.models import AMPServer, AMPServerMetric

class Command(BaseCommand):
    help = 'Fetch AMP server data and IGDB cover art, store in database'

    def get_twitch_token(self):
        """Get Twitch OAuth token for IGDB API"""
        TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
        TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
        
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        
        response = requests.post(url, params=params)
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            self.stdout.write(self.style.ERROR(f"Failed to get Twitch token: {response.text}"))
            return None

    def get_game_id(self, game_name, token):
        """Search IGDB games endpoint for game ID"""
        TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
        url = "https://api.igdb.com/v4/games"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }
        
        query = f'search "{game_name}"; fields id, name; limit 5;'
        response = requests.post(url, headers=headers, data=query)
        
        data = response.json()
        if data and len(data) > 0:
            return data[0].get('id')
        return None

    def fetch_igdb_cover(self, game_id, token):
        """Query IGDB covers by game ID"""
        TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
        url = "https://api.igdb.com/v4/covers"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }
        
        query = f'where game = {game_id}; fields image_id, game; limit 1;'
        response = requests.post(url, headers=headers, data=query)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0].get('image_id')
        return None

    def download_and_save_cover(self, image_id, game_name):
        """Download cover image and save to staticfiles"""
        if not image_id:
            return None
        
        images_dir = Path('/app/staticfiles/images')
        images_dir.mkdir(parents=True, exist_ok=True)
        
        image_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
        
        safe_name = "".join(c for c in game_name if c.isalnum() or c in ('-', '_')).lower()
        filename = f"{safe_name}_{image_id[:8]}.jpg"
        filepath = images_dir / filename
        
        if filepath.exists():
            return f"/static/images/{filename}"
        
        try:
            urllib.request.urlretrieve(image_url, filepath)
            return f"/static/images/{filename}"
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Failed to download cover: {e}"))
            return None

    def delete_cover_image(self, cover_path):
        """Delete cover image file"""
        if not cover_path:
            return
        
        try:
            filename = cover_path.split('/')[-1]
            filepath = Path('/app/staticfiles/images') / filename
            
            if filepath.exists():
                filepath.unlink()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Failed to delete cover: {e}"))

    def handle(self, *args, **options):
        AMP_URL = os.getenv('AMP_URL', 'https://amp.beerandrevolution.net')
        AMP_USER = os.getenv('AMP_USER')
        AMP_PASS = os.getenv('AMP_PASS')

        requests.packages.urllib3.disable_warnings()

        login_url = f"{AMP_URL}/API/Core/Login"
        login_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        login_payload = {
            "username": AMP_USER,
            "password": AMP_PASS,
            "token": "",
            "rememberMe": False
        }
        login_resp = requests.post(login_url, json=login_payload, headers=login_headers, verify=False)
        login_data = login_resp.json()

        if not login_data.get('success'):
            self.stdout.write(self.style.ERROR(f"Login failed: {login_data}"))
            return

        auth_token = login_resp.headers.get('Authorization', '').replace('Bearer ', '')

        instances_url = f"{AMP_URL}/API/ADSModule/GetInstances"
        headers = {
            "Accept": "application/json",
            "User-Agent": "BeerandRevolution/1.0",
            "Authorization": f"Bearer {auth_token}"
        }
        payload = {"ForceIncludeSelf": False}

        instances_resp = requests.post(instances_url, json=payload, headers=headers, verify=False)
        instances_data = instances_resp.json()

        if not isinstance(instances_data, list):
            self.stdout.write(self.style.ERROR(f'Invalid response: {instances_data}'))
            return

        current_instance_ids = set()
        games_without_covers = []
        
        for target in instances_data:
            for instance in target.get('AvailableInstances', []):
                instance_id = instance['InstanceID']
                current_instance_ids.add(instance_id)
                
                metrics = instance.get('Metrics', {})
                cpu = metrics.get('CPU Usage', {}).get('RawValue', 0)
                memory = metrics.get('Memory Usage', {}).get('RawValue', 0)
                users = metrics.get('Active Users', {}).get('RawValue', 0)

                server, created = AMPServer.objects.update_or_create(
                    instance_id=instance_id,
                    defaults={
                        'instance_name': instance['InstanceName'],
                        'friendly_name': instance['FriendlyName'],
                        'module': instance['Module'],
                        'module_display_name': instance.get('ModuleDisplayName', ''),
                        'ip': instance['IP'],
                        'port': instance['Port'],
                        'running': instance['Running'],
                        'app_state': instance['AppState'],
                        'cpu_usage_percent': cpu,
                        'memory_usage_mb': memory,
                        'active_users': users,
                    }
                )

                AMPServerMetric.objects.create(
                    server=server,
                    cpu_usage_percent=cpu,
                    memory_usage_mb=memory,
                    active_users=users
                )
                
                if server.is_game() and not server.cover_fetched:
                    games_without_covers.append(server)

        deleted_servers = AMPServer.objects.exclude(instance_id__in=current_instance_ids)
        for server in deleted_servers:
            if server.cover_image:
                self.delete_cover_image(server.cover_image)
            server.delete()

        if games_without_covers:
            twitch_token = self.get_twitch_token()
            
            if twitch_token:
                for server in games_without_covers:
                    game_name = server.module_display_name or server.friendly_name
                    game_id = self.get_game_id(game_name, twitch_token)
                    
                    if game_id:
                        image_id = self.fetch_igdb_cover(game_id, twitch_token)
                        
                        if image_id:
                            cover_path = self.download_and_save_cover(image_id, game_name)
                            server.cover_image = cover_path
                    
                    server.cover_fetched = True
                    server.save()

        self.stdout.write(self.style.SUCCESS('Complete'))
