## Development Quickstart

This guide walks through running the project locally for development.

### Prerequisites
- Git
- Python 3.12

### Installing Python 3.12 (if not already installed)

Check your Python version:
```bash
python --version
```

If Python 3.12 is not installed, follow the instructions for your operating system.

macOS:
- Install Homebrew if you do not have it: https://brew.sh
- Then run:
```bash
brew install python@3.12
```

Linux (Ubuntu or Debian-based):
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

Windows:
- Download the Python 3.12 installer from https://www.python.org/downloads/
- Run the installer and **make sure to check “Add Python to PATH”**
- Verify installation in PowerShell:
```powershell
py -3.12 --version
```

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
If the project has a `pyproject.toml`:
```bash
pip install .
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

This setup uses Django’s built-in development server and is intended for local development only.
