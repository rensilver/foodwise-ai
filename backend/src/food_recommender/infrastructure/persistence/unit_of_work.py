"""Shared repository transaction with explicit commit and rollback by default."""

from types import TracebackType

from psycopg import Error as PsycopgError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.application.auth.ports import AdminRepository
from food_recommender.application.catalog.ports import CatalogRepository
from food_recommender.application.conversations.ports import ConversationRepository
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media.cleanup_ports import MediaCleanupRepository
from food_recommender.application.media.ports import MediaRepository
from food_recommender.application.trends.ports import TrendRepository
from food_recommender.infrastructure.persistence.repositories.admin import (
    PostgresAdminRepository,
)
from food_recommender.infrastructure.persistence.repositories.catalog import (
    PostgresCatalogRepository,
)
from food_recommender.infrastructure.persistence.repositories.conversations import (
    PostgresConversationRepository,
)
from food_recommender.infrastructure.persistence.repositories.media import (
    PostgresMediaRepository,
)
from food_recommender.infrastructure.persistence.repositories.media_cleanup import (
    PostgresMediaCleanupRepository,
)
from food_recommender.infrastructure.persistence.repositories.trends import (
    PostgresTrendRepository,
)


class PostgresUnitOfWork:
    media: MediaRepository
    admin: AdminRepository
    catalog: CatalogRepository
    conversations: ConversationRepository
    trends: TrendRepository
    cleanup: MediaCleanupRepository

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "PostgresUnitOfWork":
        if self.session is not None:
            raise RuntimeError("Unit of work cannot be reentered")
        self.session = self.sessions()
        await self.session.begin()
        self.admin = PostgresAdminRepository(self.session)
        self.media = PostgresMediaRepository(self.session)
        self.catalog = PostgresCatalogRepository(self.session)
        self.conversations = PostgresConversationRepository(self.session)
        self.trends = PostgresTrendRepository(self.session)
        self.cleanup = PostgresMediaCleanupRepository(self.session)
        return self

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self.session.commit()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is not None:
            try:
                await self.session.rollback()
            finally:
                await self.session.close()
                self.session = None
        if isinstance(exc, IntegrityError):
            code = (
                ErrorCode.CONFLICT
                if getattr(exc.orig, "sqlstate", None) == "23505"
                else ErrorCode.INVALID_REQUEST
            )
            raise ApplicationError(code) from exc
        if isinstance(exc, (SQLAlchemyError, PsycopgError)):
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from exc
