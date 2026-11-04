# MERN Dev Agent

An AI-powered tool that generates full MERN stack projects from a natural-language description. Built with FastAPI, LangGraph and React.

## What it does
- Generates a MERN project from a prompt, streaming progress to the UI (SSE)
- View and edit the generated files
- Generate tests for the project
- Export to GitHub and deploy to Render
- JWT authentication and project history

## How it works
The backend uses a LangGraph agent that calls Groq's hosted LLaMA 3.3 70B through the API. It consumes a model; it does not train or serve one.

## Stack
FastAPI, LangGraph, langchain-groq, MongoDB, React, Vite, TypeScript.

## Requirements
Python 3.x, Node.js, git, a MongoDB instance, and a Groq API key.

## Setup
1. `cp .env.example backend/.env` and fill in your values
2. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000`
3. Frontend: `cd frontend && npm install && npm run dev`

## Environment variables
See `.env.example`.

## Status and roadmap
See [ROADMAP.md](ROADMAP.md).

## License
MIT
