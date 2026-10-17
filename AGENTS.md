
# Portfolio Chatbot — Development Instructions

## Project Overview
This repository contains the Python AWS Lambda backend for the AI chatbot on gabrielbisco.com.

The frontend is a separate React/Vite repository.

## Architecture
- Google Identity Services handles visitor sign-in.
- AWS Lambda verifies Google ID tokens and processes authorized requests.
- DynamoDB enforces per-account and project-wide usage limits.
- Google Conversational Agents (Dialogflow CX) manages the AI agent, portfolio knowledge, and conversation state.
- The frontend uses assistant-ui, an existing React chat interface.

Do not introduce LangChain, n8n, or custom LLM conversation management.

## Python Structure
- `src/handler.py`: Thin AWS Lambda entry point.
- `src/config.py`: Application configuration.
- `src/auth/google_auth.py`: Verify Google identity tokens.
- `src/auth/session.py`: Manage secure conversation-session ownership.
- `src/chat/chat_service.py`: Coordinate chat requests.
- `src/chat/validation.py`: Validate message structure and size.
- `src/chat/rate_limit.py`: Enforce usage quotas.
- `src/chat/cx_client.py`: Communicate with Google CX.

## Security Requirements
- Never trust user identities or session IDs supplied by the browser without verification.
- Enforce per-account and project-wide quotas before calling Google CX.
- Use atomic operations for quota enforcement.
- Keep credentials and secrets out of source code and the frontend.
- Validate request sizes and formats.
- Do not expose privileged Google Cloud credentials to visitors.

## Development Guidelines
- Keep modules focused and simple.
- Avoid unnecessary abstractions and dependencies.
- Write unit tests for new application logic.
- Use Docker for local testing.
- Make small, focused changes.
- Explain architectural changes before implementing them.
- Do not modify the frontend repository.
