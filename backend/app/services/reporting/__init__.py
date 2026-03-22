__all__ = [
    "HistoryAnalyticsService",
    "HistoryIndexData",
    "HistoryRepository",
    "HistoryIndexService",
    "HistoryResultRecord",
    "HistoryRunRecord",
    "HistoryService",
    "ReportStorageService",
    "ReportEntry",
    "ReportSummary",
    "ReportsRepository",
    "StorageContext",
]


def __getattr__(name: str):
    if name == "HistoryAnalyticsService":
        from .analytics import HistoryAnalyticsService

        return HistoryAnalyticsService
    if name == "StorageContext":
        from .context import StorageContext

        return StorageContext
    if name == "HistoryService":
        from .history import HistoryService

        return HistoryService
    if name == "HistoryIndexService":
        from .history_index import HistoryIndexService

        return HistoryIndexService
    if name in {
        "HistoryIndexData",
        "HistoryResultRecord",
        "HistoryRunRecord",
        "ReportEntry",
        "ReportSummary",
    }:
        from . import models

        return getattr(models, name)
    if name in {"HistoryRepository", "ReportsRepository"}:
        from . import repositories

        return getattr(repositories, name)
    if name == "ReportStorageService":
        from .reports import ReportStorageService

        return ReportStorageService
    raise AttributeError(name)
