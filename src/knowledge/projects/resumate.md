# Resumate — Project Knowledge

**Project type:** Browser extension, AI-assisted document generation, workflow automation  
**Primary delivery:** Local Chrome extension with a Python API backend  
**Core stack:** JavaScript, Chrome Extension Manifest V3, Python, FastAPI, Pydantic, OpenAI API, PyMuPDF, Jinja2, FPDF/PDF generation  
**Related components:** OpenAI embeddings, cosine-similarity job matching, SerpAPI job collection  
**Historical stack (earlier iterations, user-confirmed):** Flask, LangChain  
**Project status:** Working local/prototype-oriented implementation with additional modules at varying levels of integration; an earlier cloud deployment was experimental and not the current supported production architecture.

## 1. Project Overview

Resumate is an AI-assisted job-application tool built around a **Chrome browser extension and a Python backend**. It aims to shorten the repetitive work of adapting an existing résumé to different job postings. A user uploads a PDF résumé, opens a job listing in the browser, and initiates a workflow that extracts job information, analyzes the candidate's background against the posting, rewrites relevant résumé sections, and returns a downloadable PDF.

A distinguishing design choice is **bring your own key (BYOK)**: the extension asks the user for an OpenAI API key, stores it in Chrome's local extension storage, and sends it to the local backend for the relevant AI requests. This avoids relying on one shared application-wide LLM key. It does **not** mean the key never leaves the browser: the backend receives the supplied key and calls OpenAI on the user's behalf.

The repository also contains supporting capabilities for résumé insights, semantic job matching using embeddings, job collection, and personalized cover-letter generation. Not all of these supporting components are exposed through the current extension popup.

## 2. Technology Stack

| Technology | Role in the project |
| --- | --- |
| **JavaScript / Chrome Extension Manifest V3** | Browser popup, options page, content-script injection, job-page extraction, downloads, and extension-local persistence. |
| **Python / FastAPI** | Local API serving résumé parsing and résumé-tailoring/PDF endpoints. |
| **Pydantic** | Structured résumé and job-posting objects; validation of LLM-generated insights, editorial suggestions, and rewritten sections. |
| **OpenAI Python SDK** | Chat-completion calls for résumé parsing and multi-step tailoring; the client defaults to `gpt-4o-mini` unless another model is supplied. |
| **PyMuPDF (`fitz`)** | Extracts text from uploaded PDF résumés. |
| **Jinja2 and text prompt templates** | Separates task-specific instructions from Python orchestration and renders contextual prompts. |
| **FPDF-style PDF generation** | Builds a downloadable résumé with section layouts, text wrapping, and page-break management. |
| **Chrome `storage.local`** | Holds the API key, original PDF, structured résumé data, and scraped job details between popup actions. |
| **OpenAI embeddings / cosine similarity** | Supporting modules for representing résumés and jobs as vectors and ranking semantic similarity. |
| **SerpAPI** | Separate collector module for Google Jobs results; not part of the demonstrated active-page extension flow. |
| **pytest** | Repository tests for agent utilities and related behavior. |

The supplied snapshot uses **FastAPI and the OpenAI SDK** for its main request path. **Earlier Resumate iterations used Flask and LangChain**, as confirmed by the project developer; these belong to the project’s development history rather than the current code snapshot. The exact historical responsibilities and migration details are not established by this archive. An earlier Google Cloud Run deployment was experimental and later withdrawn rather than maintained as a secured public service.

## 3. Features & Functionality

**Browser-driven application flow**

1. **User-provided API credentials:** An options page or contextual prompt collects an OpenAI API key; the extension caches it in Chrome storage.
2. **PDF résumé intake:** The user selects a PDF through the extension. The client enforces a 5 MB upload size limit and can replace a previously cached résumé.
3. **Résumé parsing:** The browser sends the PDF and API key to `POST /parse-resume`. The backend extracts its text and asks the LLM to convert it into structured résumé fields.
4. **Local résumé state:** The original PDF and parsed résumé JSON are cached for reuse, avoiding the need to upload the document for each job posting.
5. **Job-page extraction:** Clicking *Tailor Resume to Page* injects a content script into the active tab. It collects the visible title, a company-name selector when available, and a capped excerpt of page text. The extracted job object is saved in extension storage.
6. **Tailoring request:** The extension submits the structured résumé, job data, and user API key to `POST /api/tailor_resume/pdf`.
7. **PDF download:** The backend returns generated PDF bytes, and the extension creates a browser download named `Tailored_Resume.pdf`.

**Additional supporting functionality:** A dedicated cover-letter creator generates a job-specific letter from candidate and posting details. Separate embedding and matching modules can compare résumés to multiple postings. These exist in the codebase but are not shown as integrated buttons or public API endpoints in the supplied extension snapshot.

## 4. Architecture & Technical Implementation

### Browser and API boundary

The Chrome extension separates user interaction (`popup.js`), user actions (`controllers/`), local persistence (`handlers/`), API requests (`services/api_client.js`), and page extraction (`utils/job_scraper.js`). The popup prevents simultaneous upload and tailoring actions through a busy-state control. The active tab is queried at runtime and a scraper is injected via `chrome.scripting.executeScript`.

The API is built with **FastAPI**, with separate routers for PDF résumé parsing and AI-assisted tailoring. The extension calls a backend at `http://localhost:8000`, reflecting its current local-first design. The backend transforms inputs into structured objects rather than passing browser JSON unchecked to every stage.

### Structured résumé representation

`Resume` and `JobPosting` Pydantic models define candidate information, experience, education, certifications, awards, projects, skills, job title, company, location, and posting description. Parsing prompts request machine-readable JSON, and the backend validates that output before further processing. The PDF parser also checks for excessively long documents (over 20 pages) and empty or non-extractable text.

### Multi-stage AI orchestration

`ResumeTailoringAgent` coordinates distinct stages rather than asking one model call to rewrite an entire résumé blindly:

1. **Insight stage:** `ResumeInsightTool` assesses candidate strengths, gaps, improvement opportunities, and alignment with the job posting. Its output is validated against a structured schema.
2. **Editorial stage:** `ResumeEditorAdvisor` decides which résumé sections need changes, returning section-specific guidance. Sections can remain untouched when no change is recommended.
3. **Section-level rewriting:** Specialized prompt builders handle the professional summary, skills, work experience, projects, education, certifications, and awards. Their outputs are parsed and validated back into expected Pydantic types.
4. **Fallback behavior:** Individual rewrite methods can retain the original section if generated content cannot be parsed or validated.
5. **Artifact generation:** The revised résumé object passes to a custom PDF renderer and is returned to the extension as a downloadable binary response.

The implementation uses separate prompt templates and dedicated service classes; **“specialized agents” here refers to task-specific LLM workflow components**, not autonomous agents with independent browsing privileges.

### Related semantic-matching pipeline

The codebase includes an `EmbeddingTool`, OpenAI embedding adapter, and `JobMatcher`. These can encode candidate/job objects into vectors, compute **cosine similarity**, sort matching jobs, and return the top *k* results. A SerpAPI-backed collector can retrieve Google Jobs listings. This is supporting functionality and should not be described as the default Chrome popup workflow without further integration evidence.

### Document rendering

The résumé PDF generator renders contact information and optional sections with custom font sizes, line-height estimation, page-break checks, text normalization, and grouping of headings with relevant content. That demonstrates document layout engineering beyond simply forwarding raw model text to the browser.

## 5. Engineering Decisions & Challenges

- **BYOK credential flow:** Per-user API credentials enable local experimentation without an application-funded shared OpenAI key. The extension stores the key locally but must transmit it to the backend for requests, making safe handling and deployment boundaries important.
- **Separation of concerns:** Extension controllers, API routers, LLM client abstraction, prompt builders, structured schemas, and output generation are separate modules, making individual workflows easier to reason about and test.
- **Structured outputs:** JSON parsing and Pydantic schemas reduce the risk of passing malformed LLM responses into document generation. Parsing fenced JSON and fallback logic address common LLM-format inconsistencies.
- **Selective editing:** The advisor stage avoids automatically rewriting every section when the job posting does not justify it, and rewrite prompts instruct the model to retain factual candidate information.
- **Source-document reuse:** Locally cached PDF and structured data allow repeated tailoring without repeated resume upload, while capturing job details from the active browser tab reduces manual copying.
- **Multi-step orchestration tradeoff:** The insight/advice/rewrite approach offers more controllable editing than a single broad prompt, at the cost of multiple LLM calls, increased latency, and greater sensitivity to prompt/response consistency.

## 6. Testing & Evaluation

The repository includes **automated tests for several agent, parsing, embedding, matching, and document-generation components**, alongside scripts for exercising external integrations. The archive does not establish a single verified coverage percentage or a repeatable end-to-end performance benchmark.

The engineering focus is on correctness of structured outputs, serialization, section-specific transformation, résumé-to-job alignment, and returning usable PDF artifacts. No validated aggregate improvement in recruiter response rate, ATS score, or application success is established by the provided source code.

## 7. Deployment, Status & Limitations

The supplied extension is designed to run with a **local FastAPI service**, with endpoints hardcoded to `localhost:8000`. An earlier cloud deployment was explored but was not retained as the project's current production setup due to security concerns. The archive itself does not contain evidence of a maintained public deployment.

This is a prototype/development-oriented codebase rather than a hardened public SaaS product. Relevant boundaries include:

- The scraper uses generalized DOM selectors and an excerpt of page text, so extraction quality varies by job site; it is not a universal structured scraper.
- The popup demonstrates résumé upload and tailoring; cover-letter generation and semantic job ranking are separate supporting modules, not fully exposed through the primary extension experience.
- Several prompt-builder functions reference templates whose names do not match all files included in the supplied archive; the complete latest tailoring path should be rechecked before describing it as production-stable. The PDF generator also imports `fpdf`, which is not listed in the supplied `requirements.txt`.
- The current local API uses permissive CORS and returns some raw exception details. Browser permissions are broad, and sensitive résumé content can appear in development logs. These would need tightening for secure public deployment.
- No verified applicant-outcome metrics or current hosted service availability are claimed.

These are implementation-status notes, not claims that every experimental feature was shipped to users.

## 8. Skills & Engineering Takeaways

Resumate demonstrates practical experience in:

- **Browser extension engineering:** Chrome Manifest V3, popup UX, dynamic content-script injection, browser permissions, local state, and file downloads.
- **API and backend development:** FastAPI routes, multipart PDF uploads, JSON request validation, binary streaming responses, and separation between frontend and backend services.
- **Applied LLM engineering:** Task-oriented prompt design, multi-stage orchestration, grounded résumé rewriting, output parsing, schema validation, and failure fallback.
- **Structured data and document processing:** PDF text extraction, typed candidate/job models, template-driven transformations, and programmatic PDF layout.
- **Embedding-based matching:** Semantic representations, cosine similarity, ranking, and job collection through a separate integration layer.
- **System design and security tradeoffs:** BYOK credentials, local-first application design, API boundaries, handling personal documents, and understanding why an experimental cloud deployment should not automatically be treated as production-ready.
- **Technology evolution:** Previous iterations used Flask and LangChain; the inspected version uses FastAPI and direct OpenAI SDK calls. These should not be presented as simultaneous dependencies of the current implementation.

**Portfolio positioning:** Resumate connects browser automation, applied generative AI, Python backend engineering, and document workflows to a concrete end-user task: tailoring job applications while preserving a structured representation of the candidate's experience.

---

## Sources & Verification (internal reference — exclude from chatbot retrieval if desired)

- `extension/manifest.json`, `extension/popup.js`, `extension/options.js`, `extension/controllers/*`, `extension/handlers/*`, `extension/services/api_client.js`, `extension/utils/job_scraper.js` — browser flow, BYOK storage, scraping, local caching, and backend communication.
- `web_api/main.py`, `web_api/routes/parser_router.py`, `web_api/routes/tailor_resume_router.py`, `web_api/models/api_resume_request.py` — FastAPI routes and request/response shapes.
- `resume_agents/parser.py`, `resume_agents/resume_schema.py`, `resume_agents/tailoring_agent/*`, `resume_agents/utils/resume_generator.py` — parsing, tailoring stages, Pydantic validation, and PDF formatting.
- `prompt_services/builders/resume_prompt_builder.py`, `prompt_services/prompts/*` — prompt architecture and section-specific templates.
- `cv_agent/cv_creator.py`, `job_agents/embedding_tool.py`, `job_agents/job_matcher.py`, `job_agents/job_collector/*`, `embedding/*` — independent cover-letter, matching, and job-collection modules.
- `requirements.txt` — bundled direct and transitive Python dependencies.
- Developer confirmation establishes historical Flask/LangChain usage; the inspected code supports FastAPI/direct OpenAI SDK usage. Historical project discussion supplied the experimental Cloud Run context; its current deployment is not independently established by this archive.
