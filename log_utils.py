import json, logging, sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
_log = logging.getLogger("airbreda")

def log_event(level: int, event: str, **fields) -> None:
    _log.log(level, json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level),
        "event": event,
        **fields,
    }, default=str))