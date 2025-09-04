from contextlib import asynccontextmanager
from typing import Dict

from asyncpg import create_pool
from asyncpg.pool import Pool

from src.config.setting import settings


class PoolCreate:
    """Connection Pool을 사용한 방식입니다."""
    def __init__(self, databases: Dict):
        self.databases = databases["DATABASE"]
        self.default = databases["default"]

    async def init(self) -> None:
        for key, value in self.databases.items():
            self.databases[key] = await create_pool(
                host=value["DB_HOST"],
                port=value["DB_PORT"],
                database=value["DB_NAME"],
                user=value["DB_USER"],
                password=value["DB_PASSWORD"],
            )

    async def release(self) -> None:
        for key, value in self.databases.items():
            await value.close()

    async def get(self, alias=None) -> Pool:
        if not alias:
            alias = self.default
        return self.databases[alias]


pool_db = PoolCreate(databases=settings.DATABASES)


async def init_pool():
    await pool_db.init()

async def release_pool():
    await pool_db.release()

@asynccontextmanager
async def connection(alias=None):
    pool = await pool_db.get(alias=alias)
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def transaction(alias=None):
    pool = await pool_db.get(alias=alias)
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn

