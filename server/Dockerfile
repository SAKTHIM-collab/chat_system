# server/Dockerfile
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app/server

# Install psycopg2-binary
# psycopg2 requires libpq-dev for compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    pip install psycopg2-binary && \
    apt-get remove -y libpq-dev gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the server source code into the container
COPY ./server/src /app/server/src

# Set environment variables for database connection


# Expose the port the server listens on
EXPOSE 12345

# Command to run the server
CMD ["python", "src/server.py"]
