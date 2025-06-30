#!/bin/bash

# deploy.sh
# This script pulls the latest Docker images and restarts the chat services.

# Define Docker Hub username and repository name
DOCKER_USERNAME="sakthim38" # CHANGE THIS TO YOUR DOCKER HUB USERNAME
IMAGE_NAME="chat-server"

# Ensure docker-compose is installed
if ! command -v docker-compose &> /dev/null
then
    echo "docker-compose could not be found, please install it."
    exit 1
fi

echo "Pulling latest Docker images from Docker Hub..."

# Pull the latest server image
docker pull ${DOCKER_USERNAME}/${IMAGE_NAME}:latest

# Pull the PostgreSQL image (if not already cached or needs update)
docker pull postgres:13

echo "Stopping and removing existing containers..."
# Stop and remove existing containers defined in docker-compose.yml, but keep volumes
docker-compose down

echo "Starting new containers with latest images..."
# Start services in detached mode (-d)
docker-compose up -d

echo "Deployment complete."
echo "Check container status with: docker-compose ps"
