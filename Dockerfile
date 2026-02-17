FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (none needed for this project)
# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY app/ ./app/

# Expose the port (default 5001, can be overridden)
EXPOSE 5001

# Run the application with gunicorn (production server)
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app.main:create_app()"]