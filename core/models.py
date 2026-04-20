from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class OccupancyType(str, Enum):
    USER_PROCESS = "user_process"
    HTTP_SYS = "http_sys"
    TIME_WAIT = "time_wait"
    CLOSE_WAIT = "close_wait"
    PERMISSION_LIMITED = "permission_limited"
    UNKNOWN = "unknown"


@dataclass
class PortRecord:
    protocol: str
    local_address: str
    local_port: int
    remote_address: str
    remote_port: Optional[int]
    state: str
    pid: Optional[int]
    process_name: str = ""
    command: str = ""
    occupancy_type: OccupancyType = OccupancyType.UNKNOWN
    advice: str = ""
    raw_line: str = ""


@dataclass
class PrivilegeInfo:
    platform_name: str
    is_elevated: bool
    label: str
    limitations: List[str] = field(default_factory=list)
