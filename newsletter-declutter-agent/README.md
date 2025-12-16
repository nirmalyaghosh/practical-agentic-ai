# Practical Agentic AI - Newsletter Declutter Agent

An AI agent that intelligently analyzes newsletter subscriptions and helps reduce the clutter by identifying which newsletters are actually read and which are just noise.

## The Problem
Our inboxes contain dozens (if not hundreds) of newsletters we subscribed to during moments of curiosity, but we seldom read most of them. Manually unsubscribing is tedious: open each email, scroll to the bottom, click unsubscribe, confirm—repeat 50+ times.

> What if an AI agent could analyze our individual reading behaviour and do this intelligently?

## The Solution

This project implements an **AI agent** (not just an AI assistant) using the **ReAct pattern** (Reasoning + Acting) to analyze newsletter subscriptions using 3 **tools** and recommend the ones to unsubscribe based on my reading behaviour:
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

### Example
(Extracts from log file)
```
2025-12-17 02:21:08,483 - __main__ - INFO - Authenticating with Gmail...
2025-12-17 02:21:08,502 - __main__ - INFO - Gmail authentication successful
2025-12-17 02:21:08,506 - __main__ - INFO - Starting newsletter analysis with GPT-4o-mini...
```
Scanning my Gmail for newsletters, using the `scan_newsletters` tool.
```
2025-12-17 02:21:08,508 - __main__ - INFO - --- Iteration 1 ---
2025-12-17 02:21:10,331 - __main__ - INFO - Finish reason: tool_calls
2025-12-17 02:21:10,331 - __main__ - INFO - Model requesting 1 tool call(s)
2025-12-17 02:21:10,331 - __main__ - INFO -    Tool: scan_newsletters
2025-12-17 02:21:10,331 - __main__ - INFO -    Args: {'days_back': 30}
2025-12-17 02:21:10,331 - newsletter_analysis - INFO - Scanning newsletters from the last 30 days...
2025-12-17 02:21:11,626 - newsletter_analysis - INFO - Found 500 recent emails to analyze
2025-12-17 02:23:09,899 - newsletter_analysis - INFO - Scan complete. Found 98 unique newsletters
2025-12-17 02:23:09,915 - __main__ - INFO -    Found 98 newsletters
```
Analyzing which newsletters I actually open, using the `analyze_engagement` tool. 
(*Note: information of some newsletters have been redacted for privacy*)
```
2025-12-17 02:23:09,919 - __main__ - INFO - --- Iteration 2 ---
2025-12-17 02:23:29,257 - __main__ - INFO - Finish reason: tool_calls
2025-12-17 02:23:29,258 - __main__ - INFO - Model requesting 1 tool call(s)
2025-12-17 02:23:29,258 - __main__ - INFO -    Tool: analyze_engagement
2025-12-17 02:23:29,258 - __main__ - INFO -    Args: {'newsletter_ids': ['professional.education@mit.edu', 'news@alphasignal.ai', 'hello@deeplearning.ai', 'pragmaticengineer+deepdives@substack.com', ... ]}
2025-12-17 02:23:29,258 - newsletter_analysis - INFO - Analyzing engagement for 98 newsletters...
2025-12-17 02:23:49,826 - newsletter_analysis - DEBUG - professional.education@mit.edu: 13/81 read (16.0%)
2025-12-17 02:24:17,918 - newsletter_analysis - DEBUG - news@alphasignal.ai: 4/100 read (4.0%)
2025-12-17 02:24:43,488 - newsletter_analysis - DEBUG - hello@deeplearning.ai: 48/100 read (48.0%)
2025-12-17 02:25:12,942 - newsletter_analysis - DEBUG - pragmaticengineer+deepdives@substack.com: 0/76 read (0.0%)
2025-12-17 02:47:46,938 - newsletter_analysis - INFO - Engagement analysis complete
2025-12-17 02:47:46,938 - __main__ - INFO -    Analyzed 98 newsletters
```
Calling tool `extract_unsubscribe_links`,
```
2025-12-17 02:47:46,949 - __main__ - INFO - --- Iteration 3 ---
2025-12-17 02:48:03,994 - __main__ - INFO - Finish reason: tool_calls
2025-12-17 02:48:03,998 - __main__ - INFO - Model requesting 1 tool call(s)
2025-12-17 02:48:04,000 - __main__ - INFO -    Tool: extract_unsubscribe_links
2025-12-17 02:48:04,003 - __main__ - INFO -    Args: {'sender_emails': ['professional.education@mit.edu', 'news@alphasignal.ai', 'hello@deeplearning.ai', 'pragmaticengineer+deepdives@substack.com', ... ]}
2025-12-17 02:48:04,006 - newsletter_analysis - INFO - Extracting unsubscribe links for 92 newsletters...
```
`Unsubscribe Recommendations` made by the ReAct agent,
```
2025-12-17 02:48:49,508 - __main__ - INFO - --- Iteration 4 ---

After analyzing your email newsletters over the past 30 days, here is a comprehensive summary of each newsletter, including engagement rates and unsubscribe links for those with low engagement.

#### Summary of Newsletters

1. **MIT Professional Education**
   - **Open Rate:** 16.0%
   - **Recommendation:** Consider Unsubscribing
   - **Unsubscribe Link:** [Unsubscribe](https://professional-education.mit.edu/listUnsubscribeHeader/u/310211/dc3edfb2384901f8a915ecf147f3c6b4d40b7a40522713cf598ac43f14b8391f/2780265407)

2. **AlphaSignal**
   - **Open Rate:** 4.0%
   - **Recommendation:** Consider Unsubscribing
   - **Unsubscribe Link:** [Unsubscribe](https://app.alphasignal.ai/us?uid=X8l85nPQnd6Evg6O&cid=7fa08da70e4db557)

3. **DeepLearning.AI**
   - **Open Rate:** 48.0%
   - **Recommendation:** Keep

4. **The Pragmatic Engineer**
   - **Open Rate:** 0.0%
   - **Recommendation:** Consider Unsubscribing
   - **Unsubscribe Link:** [Unsubscribe](https://newsletter.pragmaticengineer.com/action/disable_email/disable?token=eyJ1c2VyX2lkIjoxMjI2NTU1MSwicG9zdF9pZCI6MTgxODA0OTQwLCJpYXQiOjE3NjU5MDQ0MDksImV4cCI6MTc5NzQ0MDQwOSwiaXNzIjoicHViLTQ1ODcwOSIsInN1YiI6ImRpc2FibGVfZW1haWwifQ.e627DHsM1CN0I4bEh5BfmuYq0YNQ-m-iRKJ3L5636ck&all_sections=true)

Feel free to unsubscribe from the newsletters you no longer find valuable using the provided links. If you have any further questions or need assistance, let me know!

2025-12-17 02:53:34,110 - __main__ - INFO - Agent completed in 4 iterations
2025-12-17 02:53:34,115 - __main__ - INFO - Newsletter analysis completed successfully!
```

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
