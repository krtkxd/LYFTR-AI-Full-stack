.PHONY: env up down test logs

env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example. Add your API keys.")

up: env
	docker compose up --build -d
	@echo "Frontend: http://localhost:3000   Backend: http://localhost:8000"

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && python -m pytest -q
