#!/usr/bin/env python
"""Docker bootstrap — one-command setup for Docker Compose."""

import subprocess
import sys


def main():
    print("=" * 50)
    print("  Enterprise AI Platform — Docker Quick Start")
    print("=" * 50)

    # 1. Start services
    print("[1/3] Starting PostgreSQL + Redis...")
    subprocess.run(["docker", "compose", "up", "-d", "postgres", "redis"], check=True)

    # 2. Wait for DB to be ready
    print("[2/3] Waiting for database...")
    subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
         "until pg_isready -U postgres; do sleep 1; done"],
        check=True,
    )

    # 3. Start backend
    print("[3/3] Starting backend...")
    subprocess.run(["docker", "compose", "up", "-d", "backend"], check=True)

    print()
    print("[✓] All services are running!")
    print("    API:  http://localhost:8000")
    print("    Docs: http://localhost:8000/docs")
    print()
    print("    docker compose logs -f    # Follow logs")
    print("    docker compose down        # Stop everything")
    print()


if __name__ == "__main__":
    main()
