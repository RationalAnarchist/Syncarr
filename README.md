# Syncarr

Syncarr is an orchestration tool for the *arr homelab ecosystem (Sonarr, Radarr, etc.). It automates the setup process by discovering existing configurations, extracting API keys, and linking the services together via their APIs.

## Tech Stack
- **Backend**: Python 3.11+ using FastAPI.
- **Frontend**: Vanilla JS with Tailwind CSS.

## Getting Started

### Prerequisites
- Python 3.11 or higher

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Usage
Open your browser and navigate to `http://localhost:8000` to view the Syncarr discovery dashboard.
