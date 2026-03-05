import re
import json

# Fix 1: Update scanner.py
with open("utils/scanner.py", "r") as f:
    content = f.read()

new_parse_settings = """def parse_settings_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

            api_key = data.get('main', {}).get('apiKey', '')

            linked_api_keys = []
            if 'radarr' in data and isinstance(data['radarr'], list):
                for instance in data['radarr']:
                    if isinstance(instance, dict) and 'apiKey' in instance:
                        linked_api_keys.append(instance['apiKey'])

            if 'sonarr' in data and isinstance(data['sonarr'], list):
                for instance in data['sonarr']:
                    if isinstance(instance, dict) and 'apiKey' in instance:
                        linked_api_keys.append(instance['apiKey'])

            if api_key:
                return {
                    "ApiKey": api_key,
                    "Port": "",
                    "UrlBase": "",
                    "LinkedApiKeys": linked_api_keys
                }
        return None
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None"""

content = re.sub(r'def parse_settings_json\(filepath\):.*?return None\s+except Exception as e:.*?return None', new_parse_settings, content, flags=re.DOTALL)

new_scan_configs = """                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "apiKey": config_data.get("ApiKey"),
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase"),
                        "linkedApiKeys": config_data.get("LinkedApiKeys", [])
                    })"""

content = re.sub(r'discovered_apps\.append\(\{.*?\}\)', new_scan_configs, content, flags=re.DOTALL)

with open("utils/scanner.py", "w") as f:
    f.write(content)

# Fix indentation in scanner
with open("utils/scanner.py", "r") as f:
    lines = f.readlines()

with open("utils/scanner.py", "w") as f:
    for line in lines:
        if line.startswith("                                        discovered_apps.append({"):
            f.write(line.replace("                                        ", "                    "))
        else:
            f.write(line)


# Fix 2: Update main.py
with open("main.py", "r") as f:
    content = f.read()

content = re.sub(
    r'class LinkOverseerrRequest\(BaseModel\):\n    api_key: str\n    port: int = 5055\n',
    'class LinkOverseerrRequest(BaseModel):\n    api_key: str\n    port: int = 5055\n    apps_to_link: list[str] = []\n',
    content
)

old_loop = """    for app in discovered_apps:
        app_name = app['app'].lower()
        if app_name in ['sonarr', 'radarr']:
            payload = {"""

new_loop = """    for app in discovered_apps:
        app_name = app['app'].lower()
        if app_name in ['sonarr', 'radarr'] and app.get('apiKey') in request.apps_to_link:
            payload = {"""

content = content.replace(old_loop, new_loop)

with open("main.py", "w") as f:
    f.write(content)
