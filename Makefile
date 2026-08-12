.PHONY: up down logs test lint migrate migration shell seed

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec api pytest tests/ -v

lint:
	docker compose exec api ruff check app/ tests/ scripts/
	docker compose exec api ruff format --check app/ tests/ scripts/

migrate:
	docker compose exec api alembic upgrade head

migration:
	@read -p "Migration message: " msg; \
	docker compose exec api alembic revision --autogenerate -m "$$msg"

shell:
	docker compose exec api python

seed:
	docker compose exec api python -m scripts.generate_synthetic_data --count 100
