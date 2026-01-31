## Development Quickstart

This guide walks through running the project locally for development.

### Prerequisites
- Python 3.12
- Git

### Clone the repository
```bash
git clone https://github.com/maximehp/capstoneDev.git
cd capstoneDev
```

### Create and activate a virtual environment
macOS or Linux:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Apply database migrations
```bash
python manage.py migrate
```

### Run the development server
```bash
python manage.py runserver
```

### Access the application
Open a browser and navigate to:
```
http://127.0.0.1:8000
```

This setup uses Django’s built-in development server and a local database, making it suitable for local testing and development only.
