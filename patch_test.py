import re

with open("test_link.py", "r") as f:
    content = f.read()

# Update test to pass apps_to_link
new_payload = """            payload = {
                "api_key": "overseerr_test_key",
                "port": 5055,
                "apps_to_link": ["test_sonarr_key", "test_radarr_key"]
            }"""

content = re.sub(
    r'            payload = \{\n                "api_key": "overseerr_test_key",\n                "port": 5055\n            \}',
    new_payload,
    content,
    flags=re.DOTALL
)

with open("test_link.py", "w") as f:
    f.write(content)
