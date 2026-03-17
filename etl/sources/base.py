from abc import ABC, abstractmethod
from typing import Any, Callable, AsyncGenerator
from models import GenericDocument


class BaseSource(ABC):
    @abstractmethod
    async def connect(self):
        """Establish connection to the source."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection to the source."""
        pass

    @abstractmethod
    async def fetch(
        self, params: dict[str, Any], progress_callback: Callable[[str, float], None]
    ) -> AsyncGenerator[GenericDocument, None]:
        """
        Generic fetch method.
        params: source-specific args (e.g. chat_ids, days_back for Telegram)
        progress_callback: function to report status ("Fetching...", 0.5)
        Yields GenericDocuments.
        """
        pass

    @abstractmethod
    async def get_dialogs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch list of dialogs/chats from the source."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for the source (e.g. 'telegram')."""
        pass
