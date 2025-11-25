# AI Customer Support Agent with RAG & Hybrid Search

Enterprise-level Telegram support bot designed to automate customer service using Retrieval-Augmented Generation (RAG). The system combines semantic search with LLM reranking to provide accurate answers from a corporate knowledge base, featuring a seamless human-escalation protocol and a full-featured admin dashboard.

## 🚀 Key Features

### AI & NLP Core

*   **Advanced RAG Pipeline:** Uses **ChromaDB** for vector storage and **OpenAI** for generation. Implements hybrid search strategies to retrieve relevant context.
*   **LLM Reranking:** Two-step retrieval process where initial results are reranked by a more powerful model (e.g., GPT-4o) to ensure high relevance.
*   **Smart "Thinking" Indicator:** Mimics human behavior by showing a typing status and localized "Thinking..." messages during complex RAG queries.
*   **Follow-up Suggestions:** Automatically generates context-aware follow-up questions to guide the user.

### Business Logic & Operations

*   **Human Escalation System:** Users can request a human operator using triggers (e.g., "call a human"). Includes queue management and operator session handling.
*   **Confidence Scoring:** If the AI's confidence score drops below a threshold (default 0.7), the system proactively suggests rephrasing or contacting support.
*   **Feedback Loop:** Built-in rating system (1-5 stars) with automated collection of text feedback for low ratings.
*   **Web Admin Panel:** A Flask-based interface to manage the knowledge base (upload PDF/DOCX), view analytics, and monitor chat history.

---

## 🛠 Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Core** | Python 3.10, Flask | Microservices architecture (Bot, Web, RAG) |
| **Interface** | python-telegram-bot | Event-driven architecture for Telegram API |
| **AI/LLM** | LangChain, OpenAI API | Orchestration of RAG flows and prompt engineering |
| **Vector DB** | ChromaDB | Storage for document embeddings and semantic search |
| **Storage** | PostgreSQL | Structured data (Users, Sessions, Analytics) |
| **Caching** | Redis | Rate limiting and distributed session locks |
| **Ops** | Docker, Nginx | Containerization and reverse proxy setup |

---

## 🏗 Architecture

The system follows a modular microservice-like pattern with clear separation of concerns:

1.  **Presentation Layer:** Handles Telegram webhooks and the Web Dashboard.
2.  **Business Logic Layer:** Manages intent detection, dialogue state, and escalation rules.
3.  **RAG Controller:**
    *   *Ingestion:* Parses PDF/DOCX/Excel -> Chunks -> Embeddings -> ChromaDB.
    *   *Retrieval:* User Query -> Vector Search -> LLM Reranker -> Context Assembly -> Response Generation.
4.  **Data Layer:** Unified access via SQLAlchemy to PostgreSQL for transactional data.

*(See `/docs/technical_documentation.md` for detailed architecture breakdown)*

---

## ⚡ Quick Start

### Prerequisites

*   Docker & Docker Compose
*   Telegram Bot Token
*   OpenAI API Key

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/ai-support-bot.git
    cd ai-support-bot
    ```

2.  **Configure Environment:**
    Create a `.env` file based on the example:

    ```bash
    TELEGRAM_BOT_TOKEN=your_token
    OPENAI_API_KEY=your_key
    # Database Config
    DB_HOST=postgres
    DB_NAME=telegram_bot
    # AI Config
    RERANKING_ENABLED=true
    CONFIDENCE_THRESHOLD=0.7
    ```

3.  **Run with Docker:**

    ```bash
    docker-compose up -d
    ```

    The system will automatically initialize the PostgreSQL schema and Vector DB.

4.  **Create Admin User:**
    Initialize the first admin for the web dashboard:

    ```bash
    docker-compose exec web-interface python create_admin.py
    ```

    *(See `/docs/admin_guide.md` for detailed auth instructions)*.

---

## 📚 Documentation

Detailed documentation (in Russian language) is available in the `/docs` directory:

*   **[Technical Documentation](docs/technical_documentation.md)**: Deep dive into the RAG pipeline, architecture modules, and data flows.
*   **[Deployment Guide](docs/deployment_guide.md)**: Production setup guide, including Nginx, SSL, backup strategies, and monitoring (Prometheus/Grafana).
*   **[Admin & Auth Guide](docs/admin_guide.md)**: Instructions for managing web users and security roles.

---

## 📊 Analytics & Monitoring

The system includes built-in observability features:

*   **Dashboard:** Real-time stats on active chats, average response confidence, and operator performance.
*   **Health Checks:** Endpoints for K8s liveness/readiness probes and database connection pool monitoring.
*   **Logging:** Structured JSON logging for integration with ELK stack.

---

## 🛡 Security

*   **Input Sanitization:** Protection against prompt injection and SQL/XSS attacks.
*   **RBAC:** Role-based access control (Admin, Operator, Viewer) for the internal dashboard.
*   **Rate Limiting:** Configurable limits for both Telegram users and Web API endpoints via Redis.

---

### Author

**Mikhail yashkinSun Lanin**
*Technical Product Manager (AI & E-com) | AI Engineer*
[LinkedIn Profile Link](https://www.linkedin.com/in/mikhail-lanin-981348339/)
