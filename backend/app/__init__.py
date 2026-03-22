__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from .main import app

        return app
    raise AttributeError(name)
