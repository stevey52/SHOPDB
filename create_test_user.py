import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoredmotors_project.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='testadmin').exists():
    User.objects.create_superuser('testadmin', 'admin@example.com', 'testpass')
    print('Superuser "testadmin" created.')
else:
    print('Superuser "testadmin" already exists.')
