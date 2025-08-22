.PHONY: help setup install activate clean test lint format run-api run-worker migrate create-migration docker-build docker-run

# Default target
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Setup and installation
setup: ## Set up the development environment
	python3 -m venv venv
	venv/bin/pip install --upgrade pip
	venv/bin/pip install -r requirements-dev.txt
	venv/bin/pre-commit install
	@echo "Development environment setup complete!"

install: ## Install dependencies only
	venv/bin/pip install -r requirements-dev.txt

activate: ## Show how to activate the virtual environment
	@echo "To activate the virtual environment, run:"
	@echo "  source venv/bin/activate"

clean: ## Clean up generated files and cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .mypy_cache/

# Testing
test: ## Run all tests
	venv/bin/pytest tests/ -v

test-unit: ## Run unit tests only
	venv/bin/pytest tests/unit/ -v

test-integration: ## Run integration tests only
	venv/bin/pytest tests/integration/ -v

test-cov: ## Run tests with coverage
	venv/bin/pytest --cov=./ --cov-report=html --cov-report=term

# Code quality
lint: ## Run linting tools
	venv/bin/flake8 .
	venv/bin/mypy .
	venv/bin/bandit -r . --exclude tests/

format: ## Format code with black and isort
	venv/bin/black .
	venv/bin/isort .

check: ## Run all code quality checks
	make lint
	make test

# Database
migrate: ## Run database migrations
	venv/bin/alembic upgrade head

create-migration: ## Create a new migration
	@read -p "Enter migration message: " message; \
	venv/bin/alembic revision --autogenerate -m "$$message"

rollback: ## Rollback last migration
	venv/bin/alembic downgrade -1

# Running the application
run-api: ## Run the FastAPI server
	venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

run-worker: ## Run a Celery worker
	venv/bin/celery -A workers.celery_app worker --loglevel=info

run-beat: ## Run Celery beat scheduler
	venv/bin/celery -A workers.celery_app beat --loglevel=info

# CLI commands
cli: ## Run the CLI application
	venv/bin/python cli.py

# Docker
docker-build: ## Build Docker image
	docker build -t email-ingestion .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env email-ingestion

docker-compose-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-compose-down: ## Stop all services
	docker-compose down

# Development workflow
dev: ## Full development setup
	make setup
	make migrate
	@echo "Development environment is ready!"
	@echo "To start developing:"
	@echo "1. make activate"
	@echo "2. make run-api  (in one terminal)"
	@echo "3. make run-worker  (in another terminal)"

# Utility
shell: ## Start an interactive Python shell
	venv/bin/ipython

notebook: ## Start Jupyter notebook
	venv/bin/jupyter notebook

# Documentation
docs-serve: ## Serve documentation locally
	venv/bin/mkdocs serve

docs-build: ## Build documentation
	venv/bin/mkdocs build

# Security
security-check: ## Run security checks
	venv/bin/safety check
	venv/bin/bandit -r . --exclude tests/
