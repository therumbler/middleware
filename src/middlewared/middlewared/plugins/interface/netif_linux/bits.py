from enum import IntEnum

__all__ = ["InterfaceCapability", "InterfaceFlags", "InterfaceV6Flags", "InterfaceLinkState", "NeighborDiscoveryFlags"]


class InterfaceCapability(IntEnum):
    pass


class InterfaceFlags(IntEnum):
    # include/uapi/linux/if.h
    UP = 1 << 0  # sysfs
    BROADCAST = 1 << 1  # volatile
    DEBUG = 1 << 2  # sysfs
    LOOPBACK = 1 << 3  # volatile
    POINTOPOINT = 1 << 4  # volatile
    NOTRAILERS = 1 << 5  # sysfs
    RUNNING = 1 << 6  # volatile
    NOARP = 1 << 7  # sysfs
    PROMISC = 1 << 8  # sysfs
    ALLMULTI = 1 << 9  # sysfs
    MASTER = 1 << 10  # volatile
    SLAVE = 1 << 11  # volatile
    MULTICAST = 1 << 12  # sysfs
    PORTSEL = 1 << 13  # sysfs
    AUTOMEDIA = 1 << 14  # sysfs
    DYNAMIC = 1 << 15  # sysfs
    LOWER_UP = 1 << 16
    DORMANT = 1 << 17
    ECHO = 1 << 18


class InterfaceV6Flags(IntEnum):
    # include/uapi/linux/if_addr.h
    TEMPORARY = int('0x01', base=16)
    NODAD = int('0x02', base=16)
    OPTIMISTIC = int('0x04', base=16)
    DADFAILED = int('0x08', base=16)
    HOMEADDRESS = int('0x10', base=16)
    DEPRECATED = int('0x20', base=16)
    TENTATIVE = int('0x40', base=16)
    PERMANENT = int('0x80', base=16)
    MANAGETEMPADDR = int('0x100', base=16)
    NOPREFIXROUTE = int('0x200', base=16)
    MCAUTOJOIN = int('0x400', base=16)
    STABLE_PRIVACY = int('0x800', base=16)


class InterfaceLinkState(IntEnum):
    LINK_STATE_UNKNOWN = 0
    LINK_STATE_DOWN = 1
    LINK_STATE_UP = 2


class NeighborDiscoveryFlags(IntEnum):
    PERFORMNUD = 0
    ACCEPT_RTADV = 0
    PREFER_SOURCE = 0
    IFDISABLED = 0
    DONT_SET_IFROUTE = 0
    AUTO_LINKLOCAL = 0
    NO_RADR = 0
    NO_PREFER_IFACE = 0
