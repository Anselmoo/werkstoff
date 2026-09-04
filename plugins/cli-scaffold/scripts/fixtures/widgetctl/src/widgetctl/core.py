"""Core logic. Zero CLI-framework imports, by doctrine."""

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_USAGE = 2


class WidgetNotFound(Exception):
    """Raised when a widget id is not present in the inventory."""


def describe(inventory, widget_id):
    """Return one widget record, or raise WidgetNotFound."""
    for widget in inventory:
        if widget["id"] == widget_id:
            return widget
    raise WidgetNotFound(widget_id)
