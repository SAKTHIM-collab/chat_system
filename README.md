task 3b:
cft web : https://github.com/SAKTHIM-collab/cft_web
cft crypto : https://github.com/SAKTHIM-collab/cft_crypto


# Secure Chat System with Docker & CI/CD

## Project Overview

This project is a robust, multi-user chat application built with Python, featuring a Dockerized architecture and an automated Continuous Integration/Continuous Deployment (CI/CD) pipeline using GitHub Actions. It supports user registration, private messaging, chat rooms, and persistent data storage via PostgreSQL.

## Features

* **User Management:** Secure registration and login for unique users.
* **Private Messaging:** Send direct messages to specific online users.
* **Chat Rooms:**
    * Create public or private chat rooms.
    * Join and leave existing rooms.
    * Send public messages within the current room (`sendall`).
* **User Presence:** View a list of currently online users.
* **User Identity:** Command to see your own logged-in username (`whoami`).
* **Leaderboard:** View top users based on:
    * Total messages sent.
    * Total active time in the chat system.
* **Room Statistics:** Get details for your current room, including:
    * Number of users currently in the room.
    * Names of users online in the room.
    * Total messages ever sent in that room.
* **Persistent Data:** All user data, messages, and room information are stored securely in a PostgreSQL database.
* **Dockerized Architecture:** The server and database components run in isolated Docker containers, ensuring consistent environments.
* **Automated CI/CD:** A GitHub Actions workflow automates the building of Docker images and their deployment to a remote server upon every push to the `main` branch.

## Architecture

The system comprises the following components:

* **Client (Python):** A simple command-line interface for users to interact with the chat server.
* **Server (Python):** Handles client connections, authentication, chat logic, and database interactions.
* **Database (PostgreSQL):** Stores user credentials, chat messages, room data, and activity statistics.
* **Docker & Docker Compose:** Used to containerize and orchestrate the server and database services.
* **GitHub Actions:** Automates the testing, building, and deployment process.
