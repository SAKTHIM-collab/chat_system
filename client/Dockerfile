# client/Dockerfile
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app/client

# Copy the client source code into the container
COPY ./src /app/client/src

# Set environment variables for server connection (used by client.py)
ENV SERVER_HOST=server 
ENV SERVER_PORT=12345


# Command to run the client (it will wait for user input)
CMD ["python", "src/client.py"]
