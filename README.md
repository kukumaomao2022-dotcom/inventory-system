# Inventory Sync System

Multi-store inventory synchronization system with event sourcing pattern.

## Features

- Event sourcing for inventory changes
- Rakuten RMS API integration
- SKU sync from Rakuten stores
- CSV import with preview
- Multi-store inventory sync
- Full audit trail

## Setup

1. Install dependencies:
```bash
pip install -e .
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Initialize database:
```bash
alembic upgrade head
```

4. Run the server:
```bash
uvicorn app.main:app --reload
```

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection URL
- `REDIS_URL` - Redis URL for Celery
- `ENVIRONMENT` - Set to "test" for test mode
- `RAKUTEN_DEFAULT_SERVICE_SECRET` - Default Rakuten service secret
- `RAKUTEN_DEFAULT_LICENSE_KEY` - Default Rakuten license key

## API Documentation

Visit `/docs` for interactive API documentation.

## Test Mode

Set `ENVIRONMENT=test` to enable test mode. Test SKU `ce1111` is always available.

## License

MIT
