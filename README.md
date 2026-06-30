# Digital Arena Backend

FastAPI backend for the Digital Arena debate platform.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up PostgreSQL database and update `.env` file:
```
DATABASE_URL=postgresql://username:password@localhost/digital_arena
SECRET_KEY=your-secret-key-here
```

3. Run the application:
```bash
uvicorn app.main:app --reload
```

## API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## Project Structure

- `app/models/`: SQLAlchemy database models
- `app/schemas/`: Pydantic schemas for request/response validation
- `app/api/`: API route handlers
- `app/core/`: Core functionality (auth, security, dependencies)
- `app/services/`: Business logic layer
- `app/config.py`: Application configuration
