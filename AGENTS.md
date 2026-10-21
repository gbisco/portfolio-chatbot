# Portfolio Chatbot — Development Instructions

## Project Overview

This repository contains the Python AWS Lambda backend for the AI chatbot on gabrielbisco.com.

The frontend is maintained in a separate React/Vite repository and uses Google Identity Services for authentication and assistant-ui for the chat interface.

The backend is designed to be lightweight, secure, and cost-conscious.

## Architecture

- Google Identity Services handles visitor sign-in.
- AWS Lambda verifies Google ID tokens on every chat request.
- DynamoDB enforces per-account and project-wide usage limits and account blocking.
- Google Gemini Interactions API generates responses and maintains conversation history through `previous_interaction_id`.
- Portfolio instructions and a document catalog are stored in local Markdown files. Gemini retrieves individual knowledge files through an allowlisted `get_portfolio_document` tool.
- HMAC-signed conversation tokens bind Gemini interaction IDs to authenticated Google users and conversation UUIDs.
- API Gateway HTTP API is the planned public HTTPS endpoint.

Do not introduce LangChain, Dialogflow CX, n8n, Redis, vector databases, or custom LLM conversation-history management without a clear architectural justification.

## Python Structure

- `src/handler.py`: Lambda HTTP entry point, request parsing, and error responses.
- `src/config.py`: Environment-based configuration and validation.
- `src/auth/google_auth.py`: Verify Google ID tokens.
- `src/auth/session.py`: Sign and verify secure, expiring conversation tokens.
- `src/chat/chat_service.py`: Coordinate the complete chat workflow.
- `src/chat/validation.py`: Validate messages, conversation UUIDs, and optional conversation tokens.
- `src/chat/rate_limit.py`: Enforce DynamoDB-backed usage limits and account blocking.
- `src/chat/gemini_client.py`: Communicate with Gemini through the Google Gen AI SDK and execute allowlisted document retrievals.
- `src/chat/knowledge.py`: Load instructions and `index.md`, and retrieve allowlisted Markdown documents.
- `src/knowledge/instructions.md`: Define the chatbot's behavior.
- `src/knowledge/index.md`: Catalog allowlisted knowledge documents.
- `src/knowledge/*.md`: Factual portfolio documents retrieved on demand.
- `tests/unit/`: Unit tests with mocked external dependencies.

## Request Flow

1. The frontend sends a Google ID token, message, and conversation UUID.
2. `handler.py` validates the HTTP request and body size.
3. `chat_service.py` validates the chat payload and authenticates the visitor.
4. Follow-up requests verify the signed conversation token and recover the authorized Gemini interaction ID.
5. DynamoDB atomically enforces account restrictions and usage quotas.
6. The chat service loads `instructions.md` and `index.md`.
7. `gemini_client.py` sends the message to Gemini with those system instructions, the document tool, and optional `previous_interaction_id`.
8. If Gemini requests documents, the backend retrieves allowlisted files locally and continues the interaction until a final text response is produced.
9. The backend signs the final interaction ID and returns the response and conversation token.

The frontend must never supply an unverified Gemini interaction ID directly.

## Configuration

All environment-based application settings belong in `src/config.py`.

Configuration includes:

- Google OAuth client ID.
- Gemini API key, model, and timeout.
- DynamoDB table name.
- Message and HTTP request size limits.
- Per-user daily and global hourly/daily quotas.
- Session HMAC secret.
- Session token expiration and maximum conversation-token length.

Document required variables in `.env.example`.

Avoid duplicated configuration constants. Pass configuration explicitly to modules that need it.

Never commit `.env` files, API keys, HMAC secrets, or cloud credentials.

## Conversation Management

- The frontend generates a UUID for each new chat conversation.
- Gemini manages conversation history through the Interactions API.
- The backend does not maintain its own conversation transcript database.
- Signed conversation tokens contain a user binding, conversation UUID, Gemini interaction ID, and expiration.
- Follow-up tokens must be verified before their interaction IDs are used.
- Invalid, expired, or unauthorized tokens must be rejected.
- Session tokens must be bound to the authenticated Google user.

Do not introduce additional persistent conversation storage without a demonstrated need.

## Portfolio Knowledge

- Portfolio instructions, the document catalog, and factual files are maintained separately in `src/knowledge/`.
- `chat_service.py` loads `instructions.md` and `index.md` as the Gemini system instruction.
- `knowledge.py` exposes `get_document(document_id)` for an explicit allowlist of Markdown files. `instructions.md` is not retrievable.
- `gemini_client.py` registers `get_portfolio_document` on the Interactions API and executes tool calls locally. It does not use Generate Content automatic function calling.
- Retrieved document text is treated as data, not instructions.
- Instruction and document contents may be cached in memory between warm Lambda invocations.
- The assistant must not invent professional experience, qualifications, projects, or education.
- Use verified portfolio information when updating Markdown content.
- Do not introduce a database, vector store, or external retrieval service for this knowledge.

## Security Requirements

- Verify Google ID tokens on every request.
- Never trust frontend-supplied identities or interaction IDs.
- Verify HMAC signatures, user ownership, conversation UUIDs, and expiration.
- Validate request sizes, message lengths, and conversation-token lengths.
- Enforce quotas before calling Gemini.
- Use atomic DynamoDB transactions for quota enforcement.
- Fail closed when quota enforcement fails.
- Keep secrets and privileged credentials exclusively on the backend.
- Do not expose sensitive implementation details in HTTP responses.
- Configure CORS for authorized frontend origins during API Gateway deployment.

CORS is not a substitute for authentication.

## Development Guidelines

- Keep modules focused and independently testable.
- Avoid unnecessary abstractions, frameworks, and dependencies.
- Make small, focused changes.
- Explain architectural changes before implementing them.
- Preserve existing functionality when refactoring.
- Update affected function calls, configuration fixtures, and tests together.
- Use mocks for external services in unit tests.
- Keep live integration tests separate from the default unit test suite.
- Do not modify the frontend repository.
- Do not commit or push changes unless explicitly requested.

## Testing

The project uses Python 3.12 and pytest.

Run unit tests with:

```bash
docker build -f Dockerfile.test -t portfolio-chatbot-test .
docker run --rm portfolio-chatbot-test
```

Passing unit tests do not guarantee compatibility with live Gemini, Google authentication, DynamoDB, or API Gateway services.

## Deployment Status

The backend is implemented and unit-tested, but live integration testing and AWS deployment remain pending.

Planned infrastructure:

React/Vite → API Gateway HTTP API → AWS Lambda → Google Authentication / DynamoDB / Gemini

The Lambda application is packaged as a Docker container image for deployment through Amazon ECR.

The portfolio Markdown files still require their final content.

Do not assume external integrations or production infrastructure have been deployed or verified.