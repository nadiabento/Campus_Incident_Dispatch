import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://users:users@localhost:2301/usersdb"
)