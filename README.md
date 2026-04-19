# 🦞 OpenClaw: The AI Interview Architect

**OpenClaw** is a professional-grade, high-scale interview preparation engine designed to transform technical training. It delivers deep-dive architectural challenges, system design solutions, and industry insights directly to WhatsApp, powered by a multi-agent AI orchestrated backend.

---

## 🚀 Key Features

*   🏗️ **Architectural Deep-Dives**: Focused on Senior+ HLD/LLD challenges (Kafka, Microservices, Scalability).
*   📱 **Stateless WhatsApp Integration**: Fully database-backed session management using PostgreSQL — scale across instances without losing pairing.
*   📊 **Smart Dashboard**: A sleek Streamlit interface for user registration, real-time configuration, and performance tracking.
*   🧠 **Multi-Agent Orchestration**: Specialized agents for Scoring, News Curation, and Architecture Visualization (DALL-E 3).
*   ♻️ **Soft-Delete & Reactivation**: Advanced user lifecycle management ensuring zero data loss for returning students.
*   🔥 **Engagement Engine**: Streak tracking, skill profiles, and adaptive difficulty based on mastery scores.

---

## 🛠️ Technology Stack

| Category | Technology |
| :--- | :--- |
| **Core** | Python 3.11+, Asyncio |
| **Interface** | Streamlit, WhatsApp (Neonize/Baileys) |
| **Database** | PostgreSQL, Redis (Caching) |
| **Intelligence** | OpenAI (GPT-4o, DALL-E 3), Pydantic AI |
| **Infrastructure** | APScheduler, Token Bucket Limiters |

---

## 📂 Project Structure

```text
openClaw/
├── app/
│   ├── agents/          # LLM Orchestrators (Scoring, News, Interview)
│   ├── api/             # FastAPI Endpoints (Internal)
│   ├── channels/        # Communication Drivers (WhatsApp, Telegram)
│   ├── core/            # Config, Logging, Utils, Limiters
│   ├── database/        # PostgreSQL Models & History Tracking
│   ├── llm/             # Provider Abstractions & Caching
│   ├── mcp/             # Model Context Protocol Integrations
│   └── services/        # Business Logic (Scheduler, Sessions, Performance)
├── dashboard.py         # Main UI (Streamlit Dashboard)
├── main.py              # Background Worker / Scheduler
├── db_init/             # Database Schemas & Migrations
└── tests/               # Comprehensive Pytest Suite
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- **Python 3.11+**
- **PostgreSQL 15+**
- **Redis Server** (for performance caching)
- **WhatsApp Account** (for pairing)

### 2. Database Initialization
Create your database and run the initialization script:
```bash
psql -U postgres -d openclaw -f db_init/postgres-init.sql
```

### 3. Environment Configuration
Create a `.env` file in the root:
```env
# LLM
OPENAI_API_KEY=your_key_here

# Database
POSTGRES_SERVER=localhost
POSTGRES_DB=openclaw
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=localhost

# Security
ADMIN_PASSWORD=your_dashboard_admin_pass
FERNET_KEY=your_encryption_key
```

### 4. Install Dependencies
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

---

## 🧪 Running the System

### 🖥️ Start the Dashboard (UI)
The dashboard handles user registration, pairing, and profile management.
```bash
streamlit run dashboard.py
```

### ⚙️ Start the Worker (Backend)
The worker handles scheduled content delivery and AI processing.
```bash
python main.py
```

### ✅ Run Verification Tests
```bash
pytest
```

---

## 🛡️ License
Professional internal tool. All rights reserved.