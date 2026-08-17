import sys
from pathlib import Path

# Add the project root to Python's import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import (
    initialize_pool,
    connection_context,
    close_pool,
)


def main() -> None:
    try:
        initialize_pool()

        with connection_context() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                result = cursor.fetchone()

        print(f"Database connection successful: {result}")

    finally:
        close_pool()


if __name__ == "__main__":
    main()