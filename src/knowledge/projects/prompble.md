# Prompble — AI Classroom Tutoring Platform

**Website:** https://prompble.com

## 1. Project Overview

**Project:** Prompble  
**Category:** Generative AI, Full-Stack Software Engineering, AI Systems Engineering, Automation  
**Status:** Deployed web application with a public demo and limited/private teacher access.

Prompble is a full-stack AI classroom platform built around teacher-controlled tutoring experiences. Teachers can configure prompts, create and test AI tutors, open classroom sessions, invite students, control student access and message limits, and review student conversations.

The project began as a smaller academic/hackathon concept and grew into a substantially larger application involving frontend development, backend APIs, relational data modeling, asynchronous workers, LLM-provider abstraction, distributed messaging, caching, realtime communication, usage controls, email delivery, automated testing, and cloud deployment.

Prompble is more than a chatbot interface. A large portion of the engineering work is in the software surrounding the model:

- teacher and student workflows
- prompt and tutor lifecycle management
- classroom/session state
- student authorization
- persistent conversation history
- asynchronous LLM generation
- background workers and retry behavior
- usage and capacity controls
- caching and distributed locking
- provider abstraction
- email invitation workflows
- realtime response updates
- deployment and service orchestration

The currently deployed version is primarily **prompt-centered**. Teachers construct the instructions that define a tutor, create a tutor from those instructions, and deploy that tutor into a temporary classroom session.

A separate planned architecture is being developed around a more persistent, **classroom-centered and course-aware AI tutoring system** using RAG, tool calling, and agentic orchestration. That work is documented separately later in this file and should not be described as currently implemented.

---

## 2. Current Technology Stack

| Technology | Role in Prompble |
| --- | --- |
| **React** | Teacher, student, account, classroom, and public web interfaces |
| **TypeScript** | Main frontend application language and typed API integration |
| **Vite** | Frontend development and production build tooling |
| **Flask** | Python backend API and application runtime |
| **SQLAlchemy** | ORM and persistence layer |
| **PostgreSQL** | Teachers, prompts, tutors, classrooms, students, chat history, usage state, and other persistent application data |
| **Redis** | Prompt caching, distributed locks, usage/rate controls, temporary state, and provider cache references |
| **RabbitMQ** | Message broker for asynchronous work |
| **Celery** | Background LLM-generation jobs |
| **Google Gemini** | Current production LLM provider |
| **OpenAI integration** | Alternative provider implementation supported by the backend abstraction |
| **Mock LLM provider** | Deterministic testing without external model calls |
| **PyMuPDF** | PDF text extraction for prompt reference material |
| **Socket.IO / WebSockets** | Realtime updates after asynchronous tutor generation |
| **Resend** | Transactional student invitation email |
| **Docker / Docker Compose** | Reproducible local multi-service development |
| **Railway** | Production application and infrastructure hosting |
| **Gunicorn** | Production Flask application server |
| **Cloudflare** | DNS/domain configuration |
| **Pytest** | Automated backend testing |
| **GitHub Actions** | Continuous integration / backend test execution |

### Production services

The Railway deployment separates major runtime responsibilities:

```text
prompble-backend
prompble-celery-worker
prompble-outbox-worker
PostgreSQL
Redis
RabbitMQ
```

This allows HTTP traffic, background generation, persistent event dispatch, storage, caching, and message-broker responsibilities to operate independently.

---

## 3. Current Product and Domain Architecture

The deployed version of Prompble is organized around the following flow:

```text
Teacher
   ↓
Prompt
   ↓
Tutor
   ↓
Classroom
   ↓
Classroom Seats
   ↓
Student Chat
```

### Prompt templates and prompts

Teachers normally begin by creating or configuring a Prompt.

Prompble includes reusable **PromptTemplate** definitions containing:

- subject/category information
- template text
- descriptions
- structured configuration schemas
- active/inactive state

Template configuration supports fields such as:

- select
- text
- textarea
- file

Teacher input is rendered into final prompt text, validated, previewed, and then saved as a teacher-owned **Prompt**.

An important architectural detail is that the saved Prompt contains the final rendered text. The Tutor does not need the original PromptTemplate at runtime.

Conceptually:

```text
PromptTemplate
      +
Teacher Configuration
      ↓
Rendered Prompt
      ↓
Saved Prompt
```

### Tutor

A **Tutor** references a saved Prompt.

The teacher can:

- name and describe the tutor
- associate it with a prompt
- provide student-facing instructions
- test the tutor before classroom deployment
- later change the prompt used by the tutor

Tutor testing uses the same LLM infrastructure as the rest of the application but is isolated from persistent student classroom chat.

### Classroom

The current **Classroom** model is effectively a temporary tutoring deployment rather than a permanent academic course.

A classroom contains concepts such as:

- teacher ownership
- tutor
- name / description
- join code
- opening and closing timestamps
- active/deleted state

Classrooms move through states conceptually similar to:

```text
standby
   ↓
open
   ↓
closed
```

The open/closed state is derived largely from timestamps rather than only from a stored status string.

### Student and ClassroomSeat

Students are reusable teacher-owned contacts.

Participation in an individual classroom is represented by **ClassroomSeat**.

A seat contains runtime controls such as:

- student
- classroom
- access-token hash
- joined/absent status
- enabled/disabled status
- message capacity
- message count
- join timestamp

This makes student chat access **seat-based**, rather than giving every student unrestricted access through a general account.

### ChatTurn and messages

A student interaction is represented through:

```text
ClassroomSeat
      ↓
ChatTurn
  ├── StudentMessage
  └── TutorMessage
```

Tutor messages also retain generation metadata where available, including provider/model and runtime/token information.

The application therefore persists structured LLM interactions rather than only storing raw chat transcripts.

---

## 4. Prompt Creation, Tutor Testing, and PDF Reference Material

Prompt creation is implemented as a separate workflow from tutor creation.

### Prompt flow

Conceptually:

```text
Select Template
      ↓
Configure Fields
      ↓
Optional PDF Input
      ↓
Render Prompt
      ↓
Validate
      ↓
Preview
      ↓
Save Prompt
```

System templates are seeded from application files and rendered using teacher configuration.

### PDF reference material

Prompble currently supports PDF reference material as part of prompt construction.

The existing flow is approximately:

```text
Teacher uploads PDF
      ↓
Validate file
      ↓
Extract text with PyMuPDF
      ↓
Use extracted content while rendering prompt
```

The application includes PDF health/size/page validation logic before processing the content.

This functionality is important but should **not** be described as RAG.

The current system does not:

- maintain persistent searchable course documents
- generate document embeddings
- store document chunks in a vector index
- dynamically retrieve relevant chunks for each student message

The PDF text is primarily incorporated during prompt construction.

### Tutor testing

Teachers can test a tutor before saving/deploying it.

Tutor testing uses:

- the selected Prompt
- prompt assembly
- LLMService
- the configured provider
- temporary conversation history
- dedicated usage controls

Tutor-test usage is separately protected through mechanisms such as:

- daily limits
- draft limits
- cooldowns
- in-progress protections

This avoids making the tutor-creation interface an unrestricted LLM endpoint.

---

## 5. Student Chat and LLM Architecture

Prompble's student chat is asynchronous.

A student message is not handled by simply calling the LLM directly inside the original HTTP request.

The main flow is approximately:

```text
Student Message
      ↓
Validate Classroom / Seat / Usage
      ↓
Create pending ChatTurn
      ↓
Persist StudentMessage
      ↓
Increment seat usage
      ↓
Create Outbox Event
      ↓
Commit
      ↓
HTTP 202 response
      ↓
Outbox Worker
      ↓
Celery Job
      ↓
Redis Lock
      ↓
Assemble LLM Context
      ↓
LLMService
      ↓
Provider
      ↓
Persist TutorMessage
      ↓
Complete ChatTurn
      ↓
Realtime update
```

This separates three concerns:

1. accepting and persisting the student's request
2. generating the tutor response
3. notifying the frontend when generation completes

### LLM provider abstraction

LLM access is separated from the classroom/chat domain.

Conceptually:

```text
Application Orchestrator
       ↓
LLMService
       ↓
ProviderFactory
       ↓
Provider
   ├── Gemini
   ├── OpenAI
   └── Mock
```

The production environment currently uses Gemini.

Provider implementations handle provider-specific concerns such as:

- SDK calls
- role conversion
- system instructions
- provider response parsing
- generation metadata
- provider-specific caching

This allowed Prompble to change model providers without rewriting the higher-level tutoring workflows.

### Prompt assembly

Student chat combines distinct instruction layers.

Conceptually:

```text
<platform_system_instructions>
    Prompble-controlled instructions
</platform_system_instructions>

<teacher_configuration>
    Teacher Prompt
</teacher_configuration>
```

Student input is then added separately.

The intended hierarchy is:

```text
Platform Instructions
       ↓
Teacher Configuration
       ↓
Student Input
```

This gives the application a controlled place for platform-level behavior instead of mixing platform policy, teacher configuration, and student text into one uncontrolled string.

### Conversation context

Prompble persists the complete student transcript in PostgreSQL, but the model does not receive the entire transcript on every request.

Current generation uses a fixed recent-history window:

```text
Last 8 completed turns
+
Current student message
```

A completed turn contains both:

```text
StudentMessage
+
TutorMessage
```

This means there is an important distinction between:

- **persistent application history**
- **LLM context sent for the current generation**

Older messages remain in the database even after they fall outside the model context.

---

## 6. Distributed Systems, Reliability, and Runtime Controls

A significant part of Prompble is the infrastructure surrounding LLM calls.

### Transactional outbox

Prompble uses an outbox pattern for asynchronous events such as:

- chat-generation requests
- student invitation delivery

Instead of changing application state and publishing to a queue as unrelated operations, the application can persist the event alongside the database transaction.

The outbox worker later dispatches the event.

This reduces failure cases such as:

```text
Database commit succeeds
but queue publishing fails
```

or the reverse.

### Celery and RabbitMQ

RabbitMQ acts as the message broker.

Celery executes background jobs such as tutor-response generation.

Generation jobs include retry behavior for provider-level failures including:

- timeouts
- provider errors

Terminal failures can be persisted rather than silently losing the student's message.

### Redis

Redis supports several runtime concerns:

- distributed chat-generation locking
- assembled prompt caching
- provider-cache references
- usage/rate protections
- invite-related locks and temporary state

A Redis lock associated with a ChatTurn helps prevent duplicate concurrent generation.

### Realtime updates

Because LLM generation occurs asynchronously, the browser needs to know when the response becomes available.

Prompble uses Socket.IO / WebSockets to publish seat-scoped updates. The database remains the source of truth; realtime delivery primarily improves responsiveness in the student UI.

---

## 7. Access Control, Usage Limits, and Application-Level AI Policy

Prompble does not rely on the LLM to enforce important product rules.

Student chat is gated by application logic.

Checks include:

- classroom currently open
- valid classroom seat
- student has joined
- seat is enabled
- message capacity has not been exhausted
- another message is not already pending

### Student access

Student invitations contain:

- classroom join code
- seat-specific token

The raw seat secret is not stored directly; the system stores a hash used for validation.

### Message limits

Each seat tracks:

```text
message_capacity
message_count
```

Teachers can therefore limit model usage for individual students.

### LLM input policies

Prompble also contains model-related limits such as:

```text
Teacher prompt:
up to 4000 words

Student message:
up to 2000 characters

Historical turns sent to the LLM:
8 completed turns
```

### Subscription / usage domain

Prompble contains infrastructure for:

- SubscriptionPlan
- TeacherPlan
- TeacherUsagePeriod

Plan rules can constrain concepts such as:

- classroom openings
- classroom duration
- seat capacity
- message capacity

Although the current portfolio/beta deployment deemphasizes subscription UI, the underlying usage-control domain remains part of the implementation.

---

## 8. Backend and Frontend Software Architecture

### Backend

The Flask backend follows a layered structure:

```text
Routes
   ↓
Schemas
   ↓
Orchestrators
   ↓
Domain / Infrastructure Services
   ↓
Repositories
   ↓
SQLAlchemy Models
   ↓
PostgreSQL
```

#### Routes

Expose HTTP endpoints and keep controller-level work relatively small.

#### Schemas

Parse request data and serialize response structures.

#### Orchestrators

Coordinate workflows involving multiple services.

Examples include orchestration for:

- prompt creation
- tutor creation/testing
- classrooms
- classroom dashboards
- chat turns
- chatroom loading
- teacher dashboards

#### Domain services

Contain reusable business rules for entities such as:

- Prompt
- Tutor
- Classroom
- ClassroomSeat
- Student

#### Infrastructure services

Handle concerns such as:

- LLM calls
- prompt assembly
- PDF processing
- Redis caching
- realtime updates
- email delivery

#### Repositories

Encapsulate database querying and persistence.

This keeps large workflows out of Flask route functions and ORM models.

### Frontend

The React/TypeScript frontend contains separate experiences for:

- public project/demo pages
- teacher authentication
- teacher dashboard
- prompt creation
- tutor creation and testing
- tutor management
- classroom creation and management
- student invitation/joining
- student chat
- teacher student directory
- transcript/history review
- account/profile management

Reusable components, API modules, page-level components, and feature-specific UI are separated rather than implementing the application as a small collection of monolithic pages.

---

## 9. Testing, Deployment, and Current Status

### Automated testing

Prompble has an extensive backend test suite covering multiple layers of the application.

Areas include:

- route behavior
- request parsing
- prompt wizard orchestration
- tutor wizard orchestration
- classroom orchestration
- classroom-seat behavior
- chat-turn orchestration
- domain services
- prompt assembly
- LLMService
- ProviderFactory
- Gemini provider
- OpenAI provider
- Mock provider
- LLM limits/policies
- Celery jobs
- outbox behavior
- LLM caching
- integration/smoke flows

The mock provider allows application behavior to be tested without requiring live external LLM calls.

GitHub Actions is used to run backend tests in CI.

### Local development

The project uses Docker Compose to reproduce the multi-service development environment.

### Production deployment

Prompble is deployed through Railway.

Current production services include:

```text
Flask backend
Celery worker
Outbox worker
PostgreSQL
Redis
RabbitMQ
```

Public endpoints include:

- https://prompble.com
- https://api.prompble.com

Cloudflare handles DNS/domain configuration.

### Current limitations

The currently deployed system:

- is primarily prompt-centered
- treats Classroom as a temporary tutoring run
- uses PDF text primarily during prompt creation
- does not implement persistent classroom RAG
- does not implement vector retrieval over uploaded course materials
- uses a fixed recent conversation window
- does not implement long-term semantic student memory
- does not have persistent course-level syllabus/lecture/assignment/exam models
- does not dynamically retrieve course documents during each student question

The application is best described as a deployed engineering / portfolio / academic project with controlled beta access, not as a large commercial education platform.

---

## 10. Engineering Decisions, Challenges, and Recruiter-Relevant Takeaways

Prompble demonstrates engineering work significantly beyond connecting a frontend to an LLM API.

### Full-stack engineering

The project integrates:

- React / TypeScript
- Flask
- PostgreSQL
- REST APIs
- teacher and student workflows
- authentication/session behavior
- persistent application state

### LLM systems engineering

Implemented LLM-related work includes:

- configurable teacher prompts
- reusable prompt templates
- prompt assembly and instruction hierarchy
- provider abstraction
- Gemini integration
- OpenAI provider support
- mock provider testing
- bounded conversation context
- provider/system-prompt caching
- generation metadata persistence
- tutor testing

### Distributed systems

The production architecture uses:

- RabbitMQ
- Celery
- transactional outbox
- Redis locks
- background workers
- retry/error handling
- realtime WebSocket notification

### Reliability and control

Prompble enforces important rules in application code rather than trusting the model:

- classroom state
- student authorization
- seat enable/disable controls
- message capacities
- prompt limits
- student-input limits
- usage limits

### Database and domain design

The system models:

- teachers
- prompt templates
- prompts
- tutors
- students
- classrooms
- seats
- chat turns
- student messages
- tutor messages
- usage/subscription state

rather than reducing all application state to chat transcripts.

### Architecture evolution

One of the project's more important engineering lessons is recognizing that the original prompt-centered model is not necessarily the best abstraction for a realistic educational assistant.

That realization led to the planned redesign below.

---

# Planned Redesign — Classroom-Centered AI Tutoring

Everything below this point describes **planned academic / research work** and is not part of the currently deployed Prompble application.

## 11. Architectural Shift

The current product is primarily a prompt-building and tutor-deployment system:

```text
Teacher
   ↓
Prompt
   ↓
Tutor
   ↓
Classroom Run
   ↓
Student Chat
```

The planned redesign changes the central abstraction.

Instead of beginning with a Prompt, the teacher would begin with a persistent **Classroom representing the actual course**:

```text
Teacher
   ↓
Classroom
   ├── Course Information
   ├── Course Materials
   └── Tutoring Sessions
          ↓
      Student Chat
```

The classroom would persist across tutoring sessions and hold course-specific context such as syllabi, lectures, assignments, quizzes, exams, reference material, and learning objectives.

The conceptual shift is:

```text
Prompt-centered tutor configuration
              ↓
Persistent AI classroom with course-aware tutoring
```

---

## 12. Planned RAG Architecture

Course documents would become persistent resources instead of being inserted into one prompt during tutor creation.

### Ingestion flow

```text
Teacher Upload
      ↓
Document Validation
      ↓
Text Extraction
      ↓
Chunking
      ↓
Embedding
      ↓
Vector Storage
      +
Structured Metadata
```

Documents and chunks would carry metadata such as:

```text
classroom_id
document_id
document_type
```

Initial document types may include:

```text
syllabus
lecture
assignment
quiz
exam
reference
```

The metadata would allow retrieval to be constrained to the correct classroom and to teacher-approved resource categories.

A teacher could configure a session such as:

```text
Allowed:
✓ syllabus
✓ lectures
✓ assignments

Restricted:
✗ quizzes
✗ exams
```

The restriction would be enforced in the retrieval layer rather than relying only on a prompt instruction.

> **The AI decides what information it needs. The application decides what information it is allowed to access.**

The final vector-storage technology has not yet been finalized. Because Prompble already uses PostgreSQL, pgvector is a strong candidate for a production-oriented implementation, while tools such as FAISS may be useful for local experimentation.

---

## 13. Planned Agentic Tutor and Orchestration

The planned architecture uses a **single tool-enabled tutor agent**.

The agent would:

- interpret the student's question
- consider teacher/session instructions
- use relevant conversation history
- decide whether course retrieval is needed
- construct retrieval queries
- use retrieved course material
- write the final tutoring response

Conceptually:

```text
Student Message
      ↓
Tutor Orchestration
  ├── Platform Instructions
  ├── Teacher Session Instructions
  ├── Student Context
  └── Available Tools
            ↓
        Tutor Agent
            ↓
   Need Course Information?
       /             \
     No               Yes
     |                 ↓
     |      search_course_material(query)
     |                 ↓
     |        Session Policy Filter
     |                 ↓
     |          RAG / Vector Search
     |                 ↓
     |        Relevant Course Chunks
     └───────────────┬─┘
                     ↓
               Tutor Response
```

The LLM determines whether retrieval is needed and what query to make. Prompble determines the classroom, resource categories, and retrieval limits.

### Agent/tool orchestration

The academic prototype is expected to investigate a framework such as **LangChain / LangGraph** or an equivalent tool-calling workflow.

The orchestration layer would coordinate a loop such as:

```text
LLM
→ tool call
→ policy enforcement
→ RAG retrieval
→ tool result
→ LLM
→ final response
```

The orchestration layer does not necessarily need to be another LLM agent. It can primarily be application logic coordinating model state, available tools, retrieval calls, and final response generation.

---

## 14. Planned Evaluation and Prototype Scope

The planned academic prototype focuses on validating the new AI architecture rather than rebuilding the entire production application.

### RAG evaluation

Retrieval will be tested using questions with known relevant source material.

Metrics include:

- Precision@k
- Recall@k
- Mean Reciprocal Rank (MRR)

Session resource restrictions will also be tested to confirm that prohibited document categories are never returned.

### Tutoring evaluation

A frontier LLM will help generate a realistic synthetic course containing:

- learning objectives
- lectures
- assignments
- quizzes/exams
- related course material

A controlled set of tutoring scenarios will compare:

```text
Current prompt-centered tutor
vs.
Proposed course-aware tutor
```

Where possible, both systems will use:

- the same underlying LLM
- equivalent tutor instructions
- the same tutoring questions

Responses will be manually scored using a standardized 1–5 rubric covering:

- course alignment
- appropriate depth and difficulty
- assignment awareness
- assessment awareness
- student-context adaptation
- grounding in course material

### Prototype scope

The final project is expected to focus on:

- classroom/course representation
- categorized course documents
- RAG ingestion
- metadata-filtered retrieval
- tutor agent/tool orchestration
- session-level resource restrictions
- student context
- quantitative retrieval evaluation
- qualitative tutoring evaluation
- Jupyter notebook analysis
- architecture documentation
- final technical report

The project does not require rebuilding teacher accounts, notification systems, subscription infrastructure, production frontend workflows, or the entire current database architecture.

Those may be revisited later if the prototype demonstrates that the new architecture is worth integrating into a future Prompble version.

---

## 15. Project Distinction

Prompble is best described as a **deployed full-stack LLM classroom application with substantial software infrastructure around controlled AI tutoring**.

The current system demonstrates integration of:

```text
Full-stack application design
+
LLM provider abstraction
+
prompt engineering
+
persistent domain state
+
student authorization
+
asynchronous generation
+
distributed workers
+
usage controls
+
realtime updates
+
automated testing
+
cloud deployment
```

The planned redesign extends that work toward:

```text
Persistent classroom/course context
+
RAG
+
tool-using tutor agent
+
agentic orchestration
+
metadata-based resource controls
+
student context
+
quantitative retrieval evaluation
+
controlled tutoring evaluation
```

The strongest engineering story is not simply that Prompble calls an LLM API. It is the surrounding system required to make LLM-powered tutoring controllable, persistent, asynchronous, testable, and increasingly aware of the actual structure of the course being taught.

---

## Source and Verification Guidance for Portfolio Chatbot

This document intentionally separates **implemented functionality** from **planned work**.

### Currently implemented

The portfolio chatbot may describe the following as existing Prompble functionality:

- deployed React / TypeScript frontend
- Flask backend
- PostgreSQL persistence
- Redis
- RabbitMQ
- Celery workers
- transactional outbox workflow
- Socket.IO realtime updates
- prompt templates
- teacher-created prompts
- tutor creation/testing
- classroom runs
- student contacts
- classroom seats
- student invitation and access controls
- message capacities
- persistent chat history
- asynchronous LLM generation
- Gemini production integration
- OpenAI provider implementation
- mock provider testing
- prompt assembly
- fixed conversation-history window
- PDF reference-material extraction
- tutor-test usage controls
- subscription/usage infrastructure
- automated backend testing
- GitHub Actions CI
- Docker / Docker Compose
- Railway deployment
- Cloudflare DNS
- Resend email delivery

### Planned / research functionality

The chatbot should identify the following as planned, experimental, or under development:

- persistent course/classroom knowledge base
- course document models
- RAG over classroom resources
- embeddings/vector search
- pgvector or FAISS
- metadata-filtered course retrieval
- `search_course_material`
- session resource-category restrictions
- course-aware tutor agent
- LangChain / LangGraph or equivalent orchestration
- advanced student memory
- the classroom-centered redesign
- planned RAG evaluation
- planned qualitative tutoring evaluation
