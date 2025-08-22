# Email & Document Ingestion System

A comprehensive system for ingesting, processing, and extracting text from emails and their attachments using multiple OCR engines and AI services.

## Overview

This project provides a complete solution for:
- **Email Ingestion**: Automated fetching of emails from Gmail with OAuth2 authentication
- **Document Processing**: Multi-engine OCR processing with intelligent fallback mechanisms
- **Text Extraction**: Support for various document formats (PDF, images, office documents)
- **Storage**: Scalable blob storage with content-based deduplication
- **API**: RESTful API for managing the ingestion pipeline
- **Background Processing**: Celery-based task processing with Redis broker
- **Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations

## Architecture

The system consists of several key components:

- **API Layer**: FastAPI-based REST endpoints for configuration and monitoring
- **Worker Layer**: Celery workers for background processing of emails and documents
- **Storage Layer**: S3-compatible blob storage with deduplication
- **Database Layer**: PostgreSQL for metadata and OCR results
- **OCR Engines**: Multiple OCR providers (Google Document AI, Azure AI, Mistral, Tesseract, PaddleOCR)

## Features

### Email Processing
- Gmail API integration with OAuth2
- Automatic label management
- Push notifications via Pub/Sub
- Deduplication based on message ID
- Attachment extraction and processing

### Document Processing
- Multi-engine OCR with fallback logic
- Content-based deduplication using SHA256
- Structured data extraction (tables, forms, key-value pairs)
- Confidence scoring and quality assessment
- Support for 50+ file formats

### Storage & Database
- S3-compatible blob storage
- PostgreSQL with comprehensive schema
- Alembic migrations for version control
- Connection pooling and retry logic

### Monitoring & Observability
- Structured logging with correlation IDs
- Metrics collection for all operations
- Health check endpoints
- Dead-letter queues for failed tasks

## Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Docker (optional, for containerized deployment)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd email-document-ingestion
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements-dev.txt
```

### 4. Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/email_ingest

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Application
APP_NAME=EmailIngestion
DEBUG=true
LOG_LEVEL=INFO

# Gmail API (get from Google Cloud Console)
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret

# OCR Engines
GOOGLE_DOCUMENT_AI_ENDPOINT=your_endpoint
AZURE_AI_ENDPOINT=your_endpoint
MISTRAL_API_KEY=your_key
```

### 5. Database Setup

```bash
# Run migrations
make migrate

# Or manually:
alembic upgrade head
```

### 6. Run the Application

```bash
# Start the API server
make run-api

# In another terminal, start a worker
make run-worker
```

## Development

### Available Make Commands

```bash
make setup          # Set up development environment
make test           # Run tests
make lint           # Run linting
make format         # Format code
make migrate        # Run database migrations
make run-api        # Start API server
make run-worker     # Start Celery worker
```

### Project Structure

```
email-document-ingestion/
├── api/                    # FastAPI application
│   ├── routes/            # API endpoints
│   └── middleware/        # Request middleware
├── workers/               # Celery workers
│   └── tasks/            # Background tasks
├── models/                # Database models
│   └── schemas/          # Pydantic schemas
├── services/              # Business logic
├── utils/                 # Utility functions
├── config/                # Configuration management
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── alembic/               # Database migrations
├── docs/                  # Documentation
└── scripts/              # Utility scripts
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=./ --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint code
flake8 .
mypy .

# Pre-commit hooks
pre-commit run --all-files
```

## API Documentation

Once the API server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Configuration

### Environment Variables

The application uses environment-based configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `CELERY_BROKER_URL` | Celery broker URL | Required |
| `CELERY_RESULT_BACKEND` | Celery result backend | Required |
| `APP_NAME` | Application name | EmailIngestion |
| `DEBUG` | Debug mode | false |
| `LOG_LEVEL` | Logging level | INFO |

### OCR Engine Configuration

Configure OCR engines in your environment:

```env
# Google Document AI
GOOGLE_DOCUMENT_AI_ENDPOINT=your_endpoint
GOOGLE_CREDENTIALS_PATH=path/to/credentials.json

# Azure AI
AZURE_AI_ENDPOINT=your_endpoint
AZURE_AI_KEY=your_key

# Mistral
MISTRAL_API_KEY=your_key

# Local OCR (Tesseract/PaddleOCR)
TESSERACT_PATH=/usr/bin/tesseract
```

## Deployment

### Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build individual images
docker build -t email-ingestion-api .
docker build -t email-ingestion-worker .
```

### Production Considerations

- Use environment-specific configurations
- Set up proper logging aggregation
- Configure monitoring and alerting
- Use managed services (RDS, ElastiCache, etc.)
- Implement proper backup strategies

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `make test`
5. Format code: `make format`
6. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests for new features
- Update documentation for API changes
- Use type hints for all function signatures
- Add docstrings for public functions and classes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions and support:
- Create an issue in the GitHub repository
- Check the [documentation](docs/) for detailed guides
- Review the API documentation for integration details
