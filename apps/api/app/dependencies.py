"""Dependency injection: Neo4j driver and PostgreSQL pool."""

from __future__ import annotations

import asyncpg
from apps.api.app.config import settings
from neo4j import AsyncDriver, AsyncGraphDatabase


class DatabaseConnections:
    """Manages database connections for the application lifespan."""

    neo4j_driver: AsyncDriver | None = None
    pg_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

    async def connect(self) -> None:
        """Establish connections to Neo4j and PostgreSQL."""
        self.neo4j_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify Neo4j connectivity
        try:
            await self.neo4j_driver.verify_connectivity()
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")
            self.neo4j_driver = None

        try:
            self.pg_pool = await asyncpg.create_pool(
                dsn=settings.postgres_dsn,
                min_size=2,
                max_size=10,
            )
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            self.pg_pool = None

    async def disconnect(self) -> None:
        """Close all database connections."""
        if self.neo4j_driver:
            await self.neo4j_driver.close()
            self.neo4j_driver = None
        if self.pg_pool:
            await self.pg_pool.close()
            self.pg_pool = None

    @property
    def neo4j_connected(self) -> bool:
        return self.neo4j_driver is not None

    @property
    def postgres_connected(self) -> bool:
        return self.pg_pool is not None


db = DatabaseConnections()
