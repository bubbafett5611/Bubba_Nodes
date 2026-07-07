from .checkpoint_preview import register_checkpoint_preview_route
from .autocomplete import register_autocomplete_routes
from .discord_webhook import register_discord_webhook_routes

__all__ = ["register_checkpoint_preview_route", "register_autocomplete_routes", "register_discord_webhook_routes"]


def register_all_routes() -> None:
    """Register all optional routes; individual route functions are idempotent."""
    import logging

    logger = logging.getLogger("bubba_nodes")
    for name, register in (
        ("checkpoint preview", register_checkpoint_preview_route),
        ("autocomplete", register_autocomplete_routes),
        ("Discord webhook", register_discord_webhook_routes),
    ):
        try:
            register()
        except Exception as error:
            logger.warning("%s routes unavailable: %s", name, error)


__all__.append("register_all_routes")
