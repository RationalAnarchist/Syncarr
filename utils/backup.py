import os
import zipfile
import datetime

def create_backup(apps, backups_dir):
    """
    Compresses config.xml and main database files (.db) into a timestamped ZIP archive.
    Preserves folder structure (e.g., sonarr/config.xml, sonarr/sonarr.db).
    """
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = os.path.join(backups_dir, f"syncarr_backup_{timestamp}.zip")

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for app in apps:
            app_name = app['app'].lower()
            config_path = app['path']
            app_dir = os.path.dirname(config_path)

            # Add config.xml
            if os.path.exists(config_path):
                arcname = os.path.join(app_name, os.path.basename(config_path))
                zipf.write(config_path, arcname)

            # Add database file e.g., sonarr.db
            db_path = os.path.join(app_dir, f"{app_name}.db")
            if os.path.exists(db_path):
                arcname = os.path.join(app_name, os.path.basename(db_path))
                zipf.write(db_path, arcname)

    return zip_filename
