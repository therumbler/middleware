from pyroute2 import NDB, IPRoute

from .address import AddressMixin
from .bridge import BridgeMixin
from .bits import InterfaceFlags, InterfaceV6Flags, InterfaceLinkState
from .lagg import LaggMixin
from .utils import bitmask_to_set, INTERNAL_INTERFACES
from .vlan import VlanMixin
from .vrrp import VrrpMixin
from .ethernet_settings import EthernetHardwareSettings

__all__ = ["Interface"]

CLONED_PREFIXES = ["br", "vlan", "bond"] + INTERNAL_INTERFACES
NDBCTX = NDB(log='off')
IPRCTX = IPRoute()


class Interface(AddressMixin, BridgeMixin, LaggMixin, VlanMixin, VrrpMixin):
    def __init__(self, name):
        self.name = name
        self.ndbinfo = NDBCTX.interfaces[self.name]
        self.iprinfo = IPRCTX.get_links(ifname=self.name)[0]

    def _read(self, name, type=str):
        return self._sysfs_read(f"/sys/class/net/{self.name}/{name}", type)

    def _sysfs_read(self, path, type=str):
        with open(path, "r") as f:
            return type(f.read().strip())

    @property
    def orig_name(self):
        return self.name

    @property
    def description(self):
        return self.name

    @description.setter
    def description(self, value):
        pass

    @property
    def mtu(self):
        return self.ndbinfo['mtu']

    @mtu.setter
    def mtu(self, mtu):
        NDBCTX.interfaces[self.name].set('mtu', mtu).commit()

    @property
    def cloned(self):
        return any((self.orig_name.startswith(i) for i in CLONED_PREFIXES))

    @property
    def flags(self):
        return bitmask_to_set(self.ndbinfo['flags'], InterfaceFlags)

    @property
    def nd6_flags(self):
        return bitmask_to_set(
            self.iprinfo.get_attr('IFLA_AF_SPEC').get_attr('AF_INET6').get_attr('IFLA_INET6_FLAGS'),
            InterfaceV6Flags
        )

    @property
    def link_state(self):
        return {
            "down": InterfaceLinkState.LINK_STATE_DOWN,
            "up": InterfaceLinkState.LINK_STATE_UP,
        }.get(self.ndbinfo['state'], InterfaceLinkState.LINK_STATE_UNKNOWN)

    @property
    def link_address(self):
        return [self.ndbinfo['address']]

    def __getstate__(self, address_stats=False, vrrp_config=None):
        state = {
            'name': self.name,
            'orig_name': self.orig_name,
            'description': self.description,
            'mtu': self.mtu,
            'cloned': self.cloned,
            'flags': [i.name for i in self.flags],
            'nd6_flags': [i.name for i in self.nd6_flags],
            'capabilities': [],
            'link_state': self.link_state.name,
            'media_type': '',
            'media_subtype': '',
            'active_media_type': '',
            'active_media_subtype': '',
            'supported_media': [],
            'media_options': None,
            'link_address': self.link_address or '',
            'aliases': [i.__getstate__(stats=address_stats) for i in self.addresses],
            'vrrp_config': vrrp_config,
        }

        with EthernetHardwareSettings(self.name) as dev:
            state.update({
                'capabilities': dev.enabled_capabilities,
                'supported_media': dev.supported_media,
                'media_type': dev.media_type,
                'media_subtype': dev.media_subtype,
                'active_media_type': dev.active_media_type,
                'active_media_subtype': dev.active_media_subtype,
            })

        if self.name.startswith('bond'):
            state.update({
                'protocol': self.protocol.name if self.protocol is not None else self.protocol,
                'ports': [{'name': p, 'flags': [x.name for x in f]} for p, f in self.ports],
                'xmit_hash_policy': self.xmit_hash_policy,
                'lacpdu_rate': self.lacpdu_rate,
            })

        if self.name.startswith('vlan'):
            state.update({
                'parent': self.parent,
                'tag': self.tag,
                'pcp': self.pcp,
            })

        return state

    def up(self):
        with NDBCTX.interfaces[self.name] as dev:
            # this context manager waits until the interface
            # is up and "ready" before exiting
            dev['state'] = 'up'

    def down(self):
        with NDBCTX.interfaces[self.name] as dev:
            dev['state'] = 'down'
