import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Backs up the SQLite database'

    def handle(self, *args, **kwargs):
        db_path = settings.DATABASES['default']['NAME']
        
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f"Database not found at {db_path}"))
            return

        # Create backups directory in base dir if it doesn't exist
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = os.path.join(backup_dir, backup_filename)

        try:
            shutil.copy2(db_path, backup_path)
            self.stdout.write(self.style.SUCCESS(f"Successfully backed up database to {backup_path}"))
            
            # Optional: Clean up old backups (keep last 7 days for instance, but for now we just keep them or keep last 10)
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.sqlite3')])
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    os.remove(os.path.join(backup_dir, old_backup))
                    self.stdout.write(f"Removed old backup {old_backup}")
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Backup failed: {str(e)}"))
