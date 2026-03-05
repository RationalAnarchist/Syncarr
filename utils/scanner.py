import os
import xml.etree.ElementTree as ET
import json

KNOWN_APPS = ['sonarr', 'radarr', 'lidarr', 'prowlarr', 'overseerr', 'readarr', 'whisparr']

def parse_config(filepath):
    """
    Parses a config.xml file to extract ApiKey, Port, and UrlBase.
    Returns a dictionary with these values or None if parsing fails.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        config_data = {}

        # Helper to extract text from a tag safely
        def get_tag_text(tag_name, default=""):
            elem = root.find(tag_name)
            return elem.text if elem is not None and elem.text else default

        api_key = get_tag_text("ApiKey")
        port = get_tag_text("Port")
        url_base = get_tag_text("UrlBase")

        # Require at least Port to be useful. ApiKey is also generally required for *arr apps.
        if port:
            config_data["ApiKey"] = api_key
            config_data["Port"] = port
            config_data["UrlBase"] = url_base
            return config_data
        return None
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def parse_settings_json(filepath):
    """
    Parses a settings.json file (e.g., from Overseerr) to extract ApiKey.
    Returns a dictionary with ApiKey, Port (empty), and UrlBase (empty) or None.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Overseerr stores its key in main.apiKey
            api_key = data.get('main', {}).get('apiKey', '')

            if api_key:
                return {
                    "ApiKey": api_key,
                    "Port": "",
                    "UrlBase": ""
                }
        return None
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def identify_app(filepath, config_data):
    """
    Guesses the app based on the directory name.
    Falls back to unknown if not in the KNOWN_APPS list.
    """
    parent_dir = os.path.basename(os.path.dirname(filepath)).lower()

    for app in KNOWN_APPS:
        if app in parent_dir:
            return app.capitalize()

    return "Unknown"

def scan_configs(base_dir):
    """
    Recursively scans base_dir for config.xml files.
    Returns a list of dictionaries with app info.
    """
    discovered_apps = []

    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} does not exist.")
        return discovered_apps

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower() == 'config.xml':
                filepath = os.path.join(root, file)
                config_data = parse_config(filepath)

                if config_data:
                    app_name = identify_app(filepath, config_data)
                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "apiKey": config_data.get("ApiKey"),
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase")
                    })
            elif file.lower() == 'settings.json':
                filepath = os.path.join(root, file)
                config_data = parse_settings_json(filepath)

                if config_data:
                    app_name = identify_app(filepath, config_data)
                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "apiKey": config_data.get("ApiKey"),
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase")
                    })

    return discovered_apps
