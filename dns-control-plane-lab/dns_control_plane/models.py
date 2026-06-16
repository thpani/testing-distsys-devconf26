from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

DnsRecordType = Literal["A", "ALIAS", "TXT"]
DnsBatchChangeType = Literal["CREATE", "DELETE", "UPSERT"]


class DnsAliasTarget(BaseModel):
    name: str
    weight: int = 100


class DnsRecord(BaseModel):
    """A simplified DNS record.

    Behaves like a small discriminated union:
    - `type == "A"`: `value` is an IPv4 address string.
    - `type == "TXT"`: `value` is a text string.
    - `type == "ALIAS"`: `value` is either one target name string or a list of
      weighted `DnsAliasTarget` fanout targets.
    """

    name: str
    type: DnsRecordType
    value: str | list[DnsAliasTarget]

    def key(self) -> str:
        return f"{self.name}|{self.type}"

    def plan_version(self) -> int | None:
        label = self.name.split(".", maxsplit=1)[0]
        try:
            if label.startswith("plan-"):
                return int(label.removeprefix("plan-"))
            if label.startswith("lb-"):
                return int(label.split("-")[1])
        except (IndexError, ValueError):
            return None
        return None


class DnsBatchChange(BaseModel):
    type: DnsBatchChangeType
    record: DnsRecord


class LoadBalancerPlanInput(BaseModel):
    id: int = Field(ge=1)
    weight: int = Field(ge=0)


class CleanupRequest(BaseModel):
    keep_last_n: int = Field(ge=0)
