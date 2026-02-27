# ./clabgen/addressing.py
def tenant_gateway_v4(cidr: str) -> str:
    base = cidr.split("/")[0]
    parts = base.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.1"


def tenant_host_ip_v4(cidr: str) -> str:
    base = cidr.split("/")[0]
    parts = base.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.2/24"


def tenant_gateway_v6(cidr: str) -> str:
    return cidr.replace("::/64", "::1")


def tenant_host_ip_v6(cidr: str) -> str:
    return cidr.replace("::/64", "::2/64")
