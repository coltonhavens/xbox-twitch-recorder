"""Conservative monthly reservations under the archive's global GCS lease."""
import datetime as dt
import time
import math
from .events import emit

GiB = 1024 ** 3
MAX_RUN_SECONDS = 6 * 3600
MONTH_SECONDS = 120 * 3600
MONTH_BYTES = 250 * GiB
FILE_BYTES = 40 * GiB
STAGING_BYTES = 100 * GiB
MAX_ATTEMPTS = 5


class GuardStop(RuntimeError):
    pass


class Budget:
    def __init__(self, store, now=None):
        self.store = store
        self.started = time.time() if now is None else now
        self.month = dt.datetime.fromtimestamp(self.started, dt.timezone.utc).strftime('%Y-%m')
        self.key = 'budget-' + self.month
        self.data = store.read(self.key)
        if not self.data:
            self.data = {'reserved_seconds': 0, 'reserved_bytes': 0}
        # Missing/malformed fields in an existing ledger must fail closed.
        if any(not isinstance(self.data.get(k), (float, int)) or not math.isfinite(self.data[k]) or self.data[k] < 0
               for k in ('reserved_seconds', 'reserved_bytes')):
            raise GuardStop('Invalid budget ledger')
        self.active_run = False

    def reserve_run(self):
        if self.data['reserved_seconds'] + MAX_RUN_SECONDS > MONTH_SECONDS:
            raise GuardStop('Monthly runtime allowance exhausted')
        self.data['reserved_seconds'] += MAX_RUN_SECONDS
        self.store.save(self.key, self.data)  # Reserve before work; killed runs keep full charge.
        self.active_run = True

    def finish_run(self, now=None):
        if self.active_run:
            elapsed = max(60, min(MAX_RUN_SECONDS, (time.time() if now is None else now) - self.started + 120))
            self.data['reserved_seconds'] -= MAX_RUN_SECONDS - elapsed
            self.store.save(self.key, self.data)
            self.active_run = False

    def reserve_download(self):
        # Charge a maximum-sized attempt even if later interrupted. Safe overcounting.
        if self.data['reserved_bytes'] + FILE_BYTES > MONTH_BYTES:
            raise GuardStop('Monthly staging download allowance exhausted')
        self.data['reserved_bytes'] += FILE_BYTES
        self.store.save(self.key, self.data)

    def downloaded(self, size):
        if not 0 < size <= FILE_BYTES:
            raise GuardStop('Invalid staged byte count')
        self.data['reserved_bytes'] -= FILE_BYTES - size
        self.store.save(self.key, self.data)

    def check_staging(self):
        total, oldest = self.store.staging_usage()
        if oldest is not None and time.time() - oldest > 24 * 3600:
            emit('staging_backlog', 'WARNING', live_bytes=total, oldest_age_hours=round((time.time() - oldest) / 3600))
        return total

    def admit_stage(self):
        total = self.check_staging()
        if total + FILE_BYTES > STAGING_BYTES:
            raise GuardStop('Staging storage allowance exhausted')
        self.reserve_download()

    def begin_attempt(self, state, video_id, now=None):
        now = time.time() if now is None else now
        if state.get('attempts', 0) >= MAX_ATTEMPTS:
            raise GuardStop('VOD attempt limit requires operator review')
        if now < state.get('retry_after', 0):
            return False
        state['attempts'] = state.get('attempts', 0) + 1
        state['retry_after'] = now + min(24 * 3600, 3600 * (2 ** (state['attempts'] - 1)))
        self.store.save(video_id, state)
        return True
