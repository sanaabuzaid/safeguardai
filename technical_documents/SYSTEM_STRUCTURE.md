# SafeGuardAI System Structure

## Overview

SafeGuardAI is a WhatsApp-based workplace safety assistant that provides workers with instant access to company safety documentation through AI-powered search and responses. Workers can ask safety questions via text or voice messages, and the system retrieves accurate information from uploaded safety manuals using Retrieval Augmented Generation (RAG).

**Key Features:**
- WhatsApp integration (no app installation required)
- Voice note support with automatic transcription
- AI-generated visual safety guides (images)
- Document-based answers (only uses uploaded company manuals)
- HSE officer dashboard for monitoring and management
- Intelligent multi-agent response system

---

## What This Document Covers

This system structure document provides a comprehensive technical overview of SafeGuardAI's architecture, including:

1. **System Architecture Diagram** - Visual representation of all components and their interactions
2. **Data Flow Processes** - How messages, voice notes, images, and documents flow through the system
3. **Core Files Reference** - Complete list of all application files and their purposes
4. **External Services** - Third-party APIs and databases used by the system
5. **Storage Locations** - Where different types of data are persisted

**Target Audience:** Developers, system administrators, and technical stakeholders who need to understand how SafeGuardAI works internally.

---

## Overview

**SafeGuardAI** is an AI-powered workplace safety assistant that operates through WhatsApp, providing workers with instant access to safety information from company documents. Workers can ask safety questions via text or voice messages, and the system retrieves relevant information from uploaded safety manuals using Retrieval Augmented Generation (RAG) technology.

### Key Capabilities

- **Document-Based Answers**: All responses come from your company's uploaded safety documents (no generic AI responses)
- **Multi-Modal Input**: Workers can type messages or send voice notes (automatically transcribed)
- **Visual Safety Guides**: Generate photorealistic safety images on request using DALL-E 3
- **Smart Agents**: Two-agent CrewAI system (Researcher + Formatter) ensures accurate, well-formatted responses
- **No App Required**: Works directly in WhatsApp - no additional app installation needed
- **HSE Dashboard**: Web-based dashboard for officers to upload documents, monitor usage, and export reports
- **Rate Limited & Secure**: Built-in rate limiting (20 messages/hour) and prompt injection detection

### How It Works

1. **Worker** sends a safety question via WhatsApp (e.g., "What PPE do I need for welding?")
2. **System** searches uploaded safety documents using semantic search (ChromaDB + OpenAI embeddings)
3. **AI Agents** extract relevant information and format it for WhatsApp (using CrewAI + GPT-4o-mini)
4. **Worker** receives accurate, source-attributed answer within 5-15 seconds
5. **HSE Officers** can monitor all conversations, upload new documents, and track usage via dashboard

### Architecture Highlights

- **Django Backend**: Handles webhooks, API endpoints, and database operations
- **RAG System**: ChromaDB for vector search with 500-character chunks and 50-character overlap
- **AI Pipeline**: Fast path for simple queries (~5s), CrewAI path for complex queries (~15s)
- **WhatsApp Integration**: Twilio handles message relay and voice note delivery
- **PostgreSQL Database**: Stores all conversations, safety logs, and document metadata
- **Persistent Vector Store**: ChromaDB stores document embeddings locally in `data/chroma/`

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          WORKER (WhatsApp)                          │
│                        Text / Voice Message                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Twilio WhatsApp    │
                    │   (Message Relay)    │
                    └──────────┬───────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DJANGO APPLICATION                          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              safety/views.py (Webhook Handler)              │  │
│  │  • Receives WhatsApp messages from Twilio                   │  │
│  │  • Spawns background thread for processing                  │  │
│  │  • Returns 200 OK immediately                               │  │
│  └────────────────────────┬────────────────────────────────────┘  │
│                           │                                        │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │          safety/security.py (Security Layer)                │  │
│  │  • Rate limiting (20 messages/hour)                         │  │
│  │  • Message length check (500 chars max)                     │  │
│  │  • Prompt injection detection                               │  │
│  └────────────────────────┬────────────────────────────────────┘  │
│                           │                                        │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │     safety/whatsapp_integration.py (Message Router)         │  │
│  │  • Classifies message (cached/general/safety)               │  │
│  │  • Handles voice transcription (Whisper)                    │  │
│  │  • Routes to appropriate handler                            │  │
│  │  • Sends response via Twilio                                │  │
│  └───────────┬──────────────────────────┬──────────────────────┘  │
│              │                          │                         │
│    ┌─────────▼─────────┐     ┌─────────▼─────────────────┐       │
│    │   Cached Reply    │     │  AI Processing Pipeline   │       │
│    │  (Greetings etc)  │     │                           │       │
│    └───────────────────┘     └─────────┬─────────────────┘       │
│                                        │                          │
│                           ┌────────────▼──────────────┐           │
│                           │  safety/ai_utils/         │           │
│                           │  rag_system.py            │           │
│                           │  • ChromaDB search        │           │
│                           │  • Document embeddings    │           │
│                           │  • Semantic retrieval     │           │
│                           └────────────┬──────────────┘           │
│                                        │                          │
│                           ┌────────────▼──────────────┐           │
│                           │  safety/ai_utils/         │           │
│                           │  agents.py                │           │
│                           │  • CrewAI orchestration   │           │
│                           │  • 2 agents (Researcher   │           │
│                           │    & Formatter)           │           │
│                           │  • GPT-4o-mini responses  │           │
│                           └────────────┬──────────────┘           │
│                                        │                          │
│                           ┌────────────▼──────────────┐           │
│                           │  safety/ai_utils/         │           │
│                           │  tools.py                 │           │
│                           │  • Whisper transcription  │           │
│                           │  • DALL-E image gen       │           │
│                           └───────────────────────────┘           │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              safety/models.py (Database)                    │  │
│  │  • User (phone, role)                                       │  │
│  │  • Document (title, file, is_active)                        │  │
│  │  • Conversation (message, response, type)                   │  │
│  │  • SafetyLog (task, safety_check, sources)                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │          safety/viewsets.py (REST API)                      │  │
│  │  • ConversationViewSet (list conversations)                 │  │
│  │  • SafetyLogViewSet (list safety logs)                      │  │
│  │  • DocumentViewSet (upload, reindex, CRUD)                  │  │
│  │  • AnalyticsViewSet (dashboard stats)                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   PostgreSQL DB      │
                    │  (Conversations,     │
                    │   Logs, Documents)   │
                    └──────────────────────┘

                    ┌──────────────────────┐
                    │   ChromaDB           │
                    │  (Vector Store at    │
                    │   data/chroma/)      │
                    └──────────────────────┘

                    ┌──────────────────────┐
                    │   OpenAI APIs        │
                    │  • GPT-4o-mini       │
                    │  • Embeddings        │
                    │  • Whisper           │
                    │  • DALL-E 3          │
                    └──────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    HSE OFFICER (Web Dashboard)                      │
│                                                                     │
│  dashboard/index.html + dashboard/static/logic.js                  │
│  • View conversations & safety logs                                │
│  • Upload/manage safety documents                                  │
│  • Analytics & usage charts (Chart.js)                             │
│  • Export CSV reports                                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Worker Asks Safety Question

```
Worker (WhatsApp) 
  → Twilio 
  → Django webhook (views.py)
  → Security checks (security.py)
  → Message classification (whatsapp_integration.py)
  → RAG search (rag_system.py) 
  → AI agents process (agents.py)
  → Response formatted
  → Twilio 
  → Worker (WhatsApp)
```

### 2. Voice Message Processing

```
Worker (WhatsApp voice note)
  → Twilio 
  → Django downloads audio
  → Whisper transcription (tools.py)
  → Processed as text message
  → [continues as text flow above]
```

### 3. Image Request

```
Worker asks "show me PPE for welding"
  → Image trigger detected
  → CrewAI formatter agent
  → DALL-E 3 generates image (tools.py)
  → URL returned with text response
  → Worker receives image + text
```

### 4. Document Upload

```
HSE Officer (Dashboard)
  → Upload .txt file
  → DocumentViewSet (viewsets.py)
  → File saved to media/documents/
  → RAG indexing (rag_system.py)
  → Text chunked (500 chars, 50 overlap)
  → Embeddings generated (OpenAI)
  → Stored in ChromaDB
```

## Core Files

### Backend (Django Core)
| File | Purpose |
|------|---------|
| `manage.py` | Django management script (runserver, migrate, etc.) |
| `backend/settings.py` | Django configuration + SAFEGUARDAI config dict |
| `backend/urls.py` | Root URL routing (admin + api) |
| `backend/wsgi.py` | WSGI entry point for production deployment |
| `backend/asgi.py` | ASGI entry point for async support |

### Safety App (Main Application)
| File | Purpose |
|------|---------|
| `safety/apps.py` | Django app configuration |
| `safety/models.py` | Database models (User, Document, Conversation, SafetyLog) |
| `safety/views.py` | Twilio webhook handler + dashboard view |
| `safety/urls.py` | Safety app URL routing |
| `safety/api_urls.py` | REST API URL routing with DRF router |
| `safety/viewsets.py` | REST API viewsets (CRUD operations) |
| `safety/serializers.py` | DRF serializers for models |
| `safety/pagination.py` | DRF pagination configuration (20 items/page, max 200) |
| `safety/admin.py` | Django admin interface configuration |
| `safety/whatsapp_integration.py` | Message routing, classification & Twilio integration |
| `safety/security.py` | Rate limiting, validation & prompt injection detection |
| `safety/migrations/0001_initial.py` | Initial database schema migration |

### AI Components
| File | Purpose |
|------|---------|
| `safety/ai_utils/rag_system.py` | ChromaDB vector search & document indexing |
| `safety/ai_utils/agents.py` | CrewAI agents (Researcher + Formatter) |
| `safety/ai_utils/tools.py` | Whisper transcription & DALL-E image generation |

### Dashboard (HSE Officers)
| File | Purpose |
|------|---------|
| `dashboard/index.html` | Dashboard HTML template |
| `dashboard/static/logic.js` | Dashboard JavaScript (data fetching, charts, CSV export) |
| `dashboard/static/design.css` | Dashboard styling (red theme) |

### Configuration Files
| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies (Django, OpenAI, CrewAI, etc.) |
| `.env.example` | Environment variables template |
| `.gitignore` | Git ignore rules (excludes .env, media/, data/, etc.) |

**Total: 26 files**

## External Services

| Service | Purpose |
|---------|---------|
| Twilio WhatsApp API | Message relay between workers and system |
| OpenAI GPT-4o-mini | Safety answer generation |
| OpenAI Embeddings | Document vectorization for search |
| OpenAI Whisper | Voice note transcription |
| OpenAI DALL-E 3 | Safety image generation |
| PostgreSQL | Persistent data storage |
| ChromaDB | Vector similarity search |

## Storage Locations

| Data | Location |
|------|----------|
| Conversations & Logs | PostgreSQL database |
| Uploaded documents | `media/documents/safety_manuals/` |
| Vector embeddings | `data/chroma/` (ChromaDB) |
| Voice files | `media/voice/` (temporary, auto-deleted) |
