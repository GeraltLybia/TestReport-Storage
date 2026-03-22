__all__ = ["HistoryService", "ReportStorageService", "StorageContext", "StorageService"]


def __getattr__(name: str):
    if name in {"HistoryService", "ReportStorageService", "StorageContext"}:
        from . import reporting

        return getattr(reporting, name)
    if name == "StorageService":
        from .storage_service import StorageService

        return StorageService
    raise AttributeError(name)
