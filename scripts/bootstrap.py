#!/usr/bin/env python
"""Bootstrap script — create .env, init DB, run migrations."""

import os
import secrets
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def generate_env():
    if os.path.exists(ENV_PATH):
        print("[✓] .env already exists — skipping")
        return

    secret_key = secrets.token_hex(32)
    env_content = f"""# === Database ===
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5432/enterprise_ai

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === Auth ===
SECRET_KEY={secret_key}

# === LLM (set your own keys) ===
OPENAI_API_KEY=
LLM_BASE_URL=
LLM_MODEL=gpt-4o-mini

# === Embedding ===
EMBEDDING_MODEL=text-embedding-3-small
"""
    with open(ENV_PATH, "w") as f:
        f.write(env_content)
    print(f"[✓] .env created at {ENV_PATH}")
    print("    >>> Edit OPENAI_API_KEY before running the app <<<")


def install_deps():
    print("[*] Installing Python dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"],
        cwd=PROJECT_ROOT,
    )
    print("[✓] Dependencies installed")


def main():
    print("=" * 50)
    print("  Enterprise AI Platform — Bootstrap")
    print("=" * 50)

    generate_env()
    install_deps()

    print()
    print("Next steps:")
    print("  1. Edit .env and set your OPENAI_API_KEY")
    print("  2. Start services:  docker compose up -d")
    print("  3. Run backend:     cd backend && uvicorn app.main:app --reload")
    print("  4. Open docs:       http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
