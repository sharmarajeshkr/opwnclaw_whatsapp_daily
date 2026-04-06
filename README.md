# OpenClaw WhatsApp Interview Bot

A professional, high-scale interview preparation bot that delivers deep-dive architectural challenges, technical solutions, and fresh industry insights directly to your WhatsApp.

## 🚀 Key Features

- **HLD/LLD Architecture Challenges**: Focused on senior-level system design including Kafka, Spring Boot, Microservices, and ML Pipelines.
- **Multi-Modal Delivery**: Every challenge includes a detailed technical solution AND an AI-generated architectural diagram (via DALL-E 3).
- **Uniqueness Engine**: Integrated history tracking ensures that questions and news items are never repeated.
- **Fresh Context**: Real-time curation of Medium.com articles and trending tech/global news with mandatory "Read more" links.
- **Dynamic Scheduling**: Configurable daily delivery (default 06:00 AM) managed via environment variables.

## 🛠️ Tech Stack

- **Python 3.x**: Core application logic.
- **Neonize (Baileys Wrapper)**: High-performance, asynchronous WhatsApp integration.
- **OpenAI (GPT-4o & DALL-E 3)**: Content generation and architectural visualization.
- **APScheduler**: Robust task scheduling for production reliability.
- **Asyncio**: Non-blocking event loop for seamless I/O operations.

## 📦 Project Structure

```text
openClaw_Interview/
├── src/
│   ├── agent.py            # AI Prompting & Content Generation
│   ├── history_manager.py  # Uniqueness & Data Persistence
│   ├── scheduler.py        # Task Orchestration & Scheduling
│   └── whatsapp_client.py  # Messaging & Image Handling
├── main.py                 # Bot Entry Point
├── data/                   # (Local Only) History & Generated Diagrams
├── .env                    # (Local Only) API Keys & Config
└── .gitignore              # Repository Security Definitions
```

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- An OpenAI API Key (with DALL-E 3 access)
- A WhatsApp account for the bot linkage

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_openai_key
WHATSAPP_TARGET_NUMBER=+91XXXXXXXXXX
WHATSAPP_SESSION_NAME=interview_bot
SCHEDULE_TIME=06:00
```

### 3. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the Bot
```bash
python main.py
```
*Note: On first run, scan the terminal's QR code with your WhatsApp app (Linked Devices).*