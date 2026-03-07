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
   python -m uvicorn main:app --host 0.0.0.0 --port 9898 --reload
   ```

### Usage
Open your browser and navigate to `http://localhost:9898` to view the Syncarr discovery dashboard.

### Docker

You can also run Syncarr using Docker.

1. Build the Docker image:
   ```bash
   docker build -t syncarr .
   ```

2. Run the Docker container:
   ```bash
   docker run -p 9898:9898 syncarr
   ```

   Then open your browser and navigate to `http://localhost:9898`.
