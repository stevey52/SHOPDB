# PythonAnywhere Deployment Guide

## Prerequisites
- PythonAnywhere account
- GitHub repository with your code

## Step 1: Clone Your Repository on PythonAnywhere

Open a Bash console on PythonAnywhere and run:

```bash
cd ~
git clone https://github.com/stevey52/SHOPDB.git
cd SHOPDB
```

## Step 2: Create a Virtual Environment

```bash
mkvirtualenv --python=/usr/bin/python3.10 shopdb-env
pip install -r requirements.txt
```

## Step 3: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

This will create a `staticfiles` directory with all your static files.

## Step 4: Run Migrations

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Step 5: Configure the Web App

Go to the **Web** tab on PythonAnywhere and:

1. Click **Add a new web app**
2. Choose **Manual configuration**
3. Select **Python 3.10**

### WSGI Configuration File

Click on the WSGI configuration file link and replace its contents with:

```python
import os
import sys

# Add your project directory to the sys.path
project_home = '/home/mtawa/SHOPDB'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variable to tell Django where your settings.py is
os.environ['DJANGO_SETTINGS_MODULE'] = 'autoredmotors_project.settings'

# Serve Django via WSGI
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Virtual Environment

Set the virtual environment path to:
```
/home/mtawa/.virtualenvs/shopdb-env
```

### Static Files Mapping

Add a static files mapping:
- **URL**: `/static/`
- **Directory**: `/home/mtawa/SHOPDB/staticfiles`

## Step 6: Reload Your Web App

Click the **Reload** button at the top of the Web tab.

## Step 7: Visit Your Site

Your app should now be live at: `https://mtawa.pythonanywhere.com`

## Updating Your App

When you make changes and push to GitHub:

```bash
# SSH into PythonAnywhere
cd ~/SHOPDB
git pull
workon shopdb-env
python manage.py collectstatic --noinput
python manage.py migrate
# Click Reload button on Web tab
```

## Troubleshooting

### Static Files Not Loading
- Verify the static files mapping in the Web tab
- Check that `collectstatic` ran successfully
- Ensure `STATIC_ROOT` is set correctly in `settings.py`

### 500 Internal Server Error
- Check the error log in the Web tab
- Verify `ALLOWED_HOSTS` includes your domain
- Ensure all migrations have run

### Database Issues
- Make sure the database file has proper permissions
- Check that migrations have been applied
