# Roadmap

MERN Dev Agent is a personal project. This is the work I plan to do next, in priority order.

## 1. Backend robustness
- [ ] Create the MongoDB client lazily (FastAPI lifespan) instead of at import time, so the app can be imported and tested without a live database
- [ ] Error handling and retries for Groq API failures and rate limits
- [ ] Input validation for generation requests
- [ ] Structured logging for each agent step

## 2. Tests
- [ ] Unit tests for each node of the LangGraph agent, with the LLM mocked
- [ ] API tests for auth and project endpoints
- [ ] Frontend component tests

## 3. Reproducibility and CI
- [ ] Dockerfile and docker-compose (backend, frontend, MongoDB)
- [ ] GitHub Actions workflow running lint and tests on every push
- [ ] Documented local setup in the README

## 4. Frontend polish
- [ ] Finish the Tailwind styling of `App.tsx`
- [ ] Loading and error states for streaming generation
- [ ] Improve the file viewer and project history

## 5. Documentation
- [ ] API documentation
- [ ] Architecture overview of the agent graph
