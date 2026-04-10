import re
import urllib.request
import urllib.parse
import json


def _normalize(name):
    return re.sub(r'[™®©]', '', name).strip()


def fetch_steam_app_id(game_name):
    variants = [game_name]
    stripped = _normalize(game_name)
    if stripped != game_name:
        variants.append(stripped)

    for variant in variants:
        try:
            encoded = urllib.parse.quote(variant)
            req = urllib.request.Request(
                f"https://store.steampowered.com/api/storesearch/?term={encoded}&cc=us&l=en",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            for item in data.get('items', []):
                if _normalize(item.get('name', '')).lower() == _normalize(variant).lower():
                    return item['id']
        except Exception:
            pass
    return None
