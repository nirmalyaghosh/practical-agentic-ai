# Practical Agentic AI - Personal LinkedIn Agent

## Setup

To set up the `Personal LinkedIn Agent` locally, follow these steps:

1. Create a Python virtual environment:
```bash
python -m venv .venv
```

2. Activate the virtual environment:
   - On Windows:
     ```bash
     .\.venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
# Next, run the following Playwright with Python to automate the browser
playwright install chromium
```

5. Set the required environment variables inside `linkedinagent.env`
```bash
OPENAI_API_KEY=sk-proj-*******************************
```

## Run the `Personal LinkedIn Agent`
```bash
python personal_li_agent.py
```