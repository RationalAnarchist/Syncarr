import os
import xml.etree.ElementTree as ET
import json

KNOWN_APPS = ['sonarr', 'radarr', 'lidarr', 'prowlarr', 'overseerr', 'readarr', 'whisparr', 'nzbget', 'qbittorrent']

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
        auth_method = get_tag_text("AuthenticationMethod")

        # Require at least Port to be useful. ApiKey is also generally required for *arr apps.
        if port:
            config_data["ApiKey"] = api_key
            config_data["Port"] = port
            config_data["UrlBase"] = url_base
            config_data["AuthenticationMethod"] = auth_method
            return config_data
        return None
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def parse_nzbget_config(filepath):
    try:
        config_data = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "ControlPort":
                        config_data["Port"] = val
                    elif key == "ControlUsername":
                        config_data["Username"] = val
                    elif key == "ControlPassword":
                        config_data["Password"] = val

        if config_data.get("Port"):
            config_data["ApiKey"] = ""
            config_data["UrlBase"] = ""
            return config_data
        return None
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def parse_qbittorrent_config(filepath):
    try:
        config_data = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    if key == r"WebUI\Port":
                        config_data["Port"] = val
                    elif key == r"WebUI\Username":
                        config_data["Username"] = val
                    elif key == r"WebUI\Password_PBKDF2":
                        config_data["Password"] = val

        if config_data.get("Port"):
            config_data["ApiKey"] = ""
            config_data["UrlBase"] = ""
            return config_data
        return None
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def parse_settings_json(filepath):
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
        return None

def identify_app(filepath, config_data, settings_data=None):
    """
    Guesses the app based on the directory name.
    Falls back to unknown if not in the KNOWN_APPS list.
    """
    if settings_data and 'app_types' in settings_data:
        if filepath in settings_data['app_types']:
            return settings_data['app_types'][filepath].capitalize()

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

    if not base_dir:
        print("Directory base_dir is empty.")
        return discovered_apps

    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} does not exist.")
        return discovered_apps

    settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")
    settings_data = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding='utf-8') as f:
                settings_data = json.load(f)
        except Exception as e:
            print(f"Error reading settings file in scanner: {e}")

    app_hostnames = settings_data.get("app_hostnames", {})

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower() == 'config.xml':
                filepath = os.path.join(root, file)
                config_data = parse_config(filepath)

                if config_data:
                    app_name = identify_app(filepath, config_data, settings_data)
                    api_key = config_data.get("ApiKey")
                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "hostname": app_hostnames.get(api_key, "localhost"),
                        "apiKey": api_key,
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase"),
                        "linkedApiKeys": config_data.get("LinkedApiKeys", []),
                        "authMethod": config_data.get("AuthenticationMethod")
                    })
            elif file.lower() == 'nzbget.conf':
                filepath = os.path.join(root, file)
                config_data = parse_nzbget_config(filepath)

                if config_data:
                    app_name = identify_app(filepath, config_data, settings_data)
                    api_key = config_data.get("ApiKey")
                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "hostname": app_hostnames.get(api_key, "localhost"),
                        "apiKey": api_key,
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase"),
                        "linkedApiKeys": config_data.get("LinkedApiKeys", []),
                        "authMethod": config_data.get("AuthenticationMethod"),
                        "username": config_data.get("Username", ""),
                        "password": config_data.get("Password", "")
                    })
            elif file.lower() == 'qbittorrent.conf':
                filepath = os.path.join(root, file)
                config_data = parse_qbittorrent_config(filepath)

                if config_data:
                    app_name = identify_app(filepath, config_data, settings_data)
                    api_key = config_data.get("ApiKey")
                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "hostname": app_hostnames.get(api_key, "localhost"),
                        "apiKey": api_key,
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase"),
                        "linkedApiKeys": config_data.get("LinkedApiKeys", []),
                        "authMethod": config_data.get("AuthenticationMethod"),
                        "username": config_data.get("Username", ""),
                        "password": config_data.get("Password", "")
                    })
            elif file.lower() == 'settings.json':
                filepath = os.path.join(root, file)
                config_data = parse_settings_json(filepath)

                if config_data:
                    app_name = identify_app(filepath, config_data, settings_data)
                    api_key = config_data.get("ApiKey")
                    discovered_apps.append({
                        "app": app_name,
                        "path": filepath,
                        "hostname": app_hostnames.get(api_key, "localhost"),
                        "apiKey": api_key,
                        "port": config_data.get("Port"),
                        "urlBase": config_data.get("UrlBase"),
                        "linkedApiKeys": config_data.get("LinkedApiKeys", []),
                        "authMethod": config_data.get("AuthenticationMethod")
                    })

    return discovered_apps
