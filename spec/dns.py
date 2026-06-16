from typing import Annotated

from wunderspec import *


TXT = Val("TXT")
A = Val("A")
CNAME = Val("CNAME")

@record
class DnsRecord(Expr):
    """A structured DNS-like record."""
    # e.g., "lock.example.com"
    name: Field[str]
    # TXT, A, CNAME
    kind: Field[str]
    # TXT: (hostname, <epoch>), A: (ip_addr, 1), CNAME: (canonical_name, weight)
    value: Field[tuple[str, int]]


def mk_txt(name: Annotated[Expr, str],
          hostname: Annotated[Expr, str],
          epoch: Annotated[Expr, str]) -> DnsRecord:
    """Helper function to create a TXT record."""
    return DnsRecord(name=name, kind=TXT, value=Tuple(hostname, epoch))


def mk_a(name: Annotated[Expr, str], ip_addr: Annotated[Expr, str]) -> DnsRecord:
    """Helper function to create an A record."""
    return DnsRecord(name=name, kind=A, value=Tuple(ip_addr, 1))


def mk_cname(name: Annotated[Expr, str],
            canonical_name: Annotated[Expr, str],
            weight: Annotated[Expr, int]) -> DnsRecord:
    """Helper function to create a CNAME record."""
    return DnsRecord(name=name, kind=CNAME, value=Tuple(canonical_name, weight))