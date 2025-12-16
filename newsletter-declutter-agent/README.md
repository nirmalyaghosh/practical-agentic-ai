# Practical Agentic AI - Newsletter Declutter Agent

An AI agent that intelligently analyzes newsletter subscriptions and helps reduce the clutter by identifying which newsletters are actually read and which are just noise.

## The Problem
Our inboxes contain dozens (if not hundreds) of newsletters we subscribed to during moments of curiosity, but we seldom read most of them. Manually unsubscribing is tedious: open each email, scroll to the bottom, click unsubscribe, confirm—repeat 50+ times.

> What if an AI agent could analyze our individual reading behaviour and do this intelligently?

## The Solution

This project implements an **AI agent** (not just an AI assistant) using the **ReAct pattern** (Reasoning + Acting) to analyze newsletter subscriptions using 3 **tools**:
- scan,
- analyze,
- extract

### Tools
- **Scan** my Gmail for newsletters using `List-Unsubscribe` headers
- **Analyze** my engagement rates (which newsletters I actually open)
- **Extract** unsubscribe links for batch action

### What Makes This "Agentic"?

Unlike a simple chatbot that responds to queries, this AI agent:

- **Plans multi-step workflows**: Decides which tools to use and in what order
- **Adapts to results**: If it finds 200 newsletters, it might filter before analyzing
- **Handles uncertainty**: Deals with API errors, rate limits, and unexpected data
- **Maintains context**: Remembers findings across multiple tool calls
- **Provides transparent reasoning**: Explains *why* it recommends each action

## Implementations
- `newsletter_declutter_openai.py`: An implementation of the AI agent using OpenAI's GPT-4o-mini with function calling.

## Setup

To set up the `Newsletter Declutter Agent` locally, follow these steps:

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
```

5. Set the required environment variables inside `newsletter-declutter-agent.env`
```bash
OPENAI_API_KEY=sk-proj-*******************************
```

## Run the `Newsletter Declutter Agent`
First, run the `gmail_auth.py` to get the token.
```bash
python gmail_auth.py
```
The token is used in subsequent calls to Gmail.
```bash
python newsletter_declutter_openai.py
```
