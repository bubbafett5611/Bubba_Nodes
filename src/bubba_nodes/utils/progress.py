from __future__ import annotations

from comfy_api.latest import ComfyAPISync


class ProgressReporter:
    def __init__(self, max_value: int) -> None:
        self.max_value = max(0, int(max_value or 0))
        self.value = 0
        self._publish()

    def update(self, increment: int = 1, *, preview_image=None) -> None:
        self.value = min(self.max_value, self.value + max(0, int(increment or 0)))
        self._publish(preview_image=preview_image)

    def _publish(self, *, preview_image=None) -> None:
        if self.max_value <= 0:
            return
        try:
            ComfyAPISync.execution.set_progress(self.value, self.max_value, preview_image=preview_image)
        except Exception:
            # Progress has no execution context during unit tests and some direct API calls.
            pass
