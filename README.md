## Development Quickstart

This guide walks through running the project locally for development.

### Prerequisites
- Git
- Python 3.12

---

### macOS / Linux

Install Python 3.12 if needed:

```bash
python3 --version
```

macOS (Homebrew):
```bash
brew install python@3.12
```

Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

Clone the repository:
```bash
git clone https://github.com/maximehp/capstoneDev.git
cd capstoneDev
```

Create and activate a virtual environment:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
python3 -m pip install -r requirements.txt
```

Run the app:
```bash
python3 manage.py migrate
python3 manage.py runserver
```

---

### Windows (PowerShell)

Verify Python 3.12:
```powershell
py -3.12 --version
```

Install Python if needed:
- Download from https://www.python.org/downloads/
- Check “Add Python to PATH” during installation

Clone the repository:
```powershell
git clone https://github.com/maximehp/capstoneDev.git
cd capstoneDev
```

Create and activate a virtual environment:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:
```powershell
py -m pip install -r requirements.txt
```

Run the app:
```powershell
py manage.py migrate
py manage.py runserver
```

---

### Access the application
```
http://127.0.0.1:8000
```

This setup uses Django’s built-in development server and is intended for local development only.
