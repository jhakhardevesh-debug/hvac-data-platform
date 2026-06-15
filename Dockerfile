# Start with official Python 3.11 slim image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Default command — runs dbt tests
CMD ["dbt", "test", "--project-dir", "hvac_dbt", "--profiles-dir", "hvac_dbt"]