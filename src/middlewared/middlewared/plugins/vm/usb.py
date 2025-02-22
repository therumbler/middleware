import re

from xml.etree import ElementTree as etree

from middlewared.schema import accepts, Bool, Dict, List, Ref, Str, returns
from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .utils import get_virsh_command_args


RE_VALID_USB_DEVICE = re.compile(r'^usb_\d+_\d+$')


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @private
    def retrieve_usb_device_information(self, xml_str):
        xml = etree.fromstring(xml_str.strip())
        capability = next((e for e in list(xml) if e.tag == 'capability'), None)
        if capability is None:
            return capability
        required_keys = set(self.get_capability_keys())
        capability_info = {}
        for element in filter(lambda e: e.tag in required_keys and e.text, capability):
            capability_info[element.tag] = element.text
            if element.tag in ('product', 'vendor') and element.get('id'):
                capability_info[f'{element.tag}_id'] = element.get('id')

        return None if set(capability_info) != required_keys else capability_info

    @private
    def get_capability_keys(self):
        return {
            'product': None,
            'vendor': None,
            'product_id': None,
            'vendor_id': None,
            'bus': None,
            'device': None,
        }

    @accepts(Str('device', empty=False))
    @returns(Dict(
        Dict(
            'capability',
            Str('product', required=True, null=True),
            Str('product_id', required=True, null=True),
            Str('vendor', required=True, null=True),
            Str('vendor_id', required=True, null=True),
            Str('bus', required=True, null=True),
            Str('device', required=True, null=True),
        ),
        Bool('available', required=True),
        Str('error', required=True, null=True),
        register=True,
    ))
    async def usb_passthrough_device(self, device):
        """
        Retrieve details about `device` USB device.
        """
        await self.middleware.call('vm.check_setup_libvirt')
        data = {
            'capability': self.get_capability_keys(),
            'available': False,
            'error': None,
        }
        cp = await run(get_virsh_command_args() + ['nodedev-dumpxml', device], check=False)
        if cp.returncode:
            data['error'] = cp.stderr.decode()
            return data

        capability_info = await self.middleware.call(
            'vm.device.retrieve_usb_device_information', cp.stdout.decode()
        )
        if not capability_info:
            data['error'] = 'Unable to determine capabilities of USB device'
        else:
            data['capability'] = capability_info

        return {
            **data,
            'available': not data['error'],
        }

    @accepts()
    @returns(List(items=[Ref('usb_passthrough_device')]))
    async def usb_passthrough_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        await self.middleware.call('vm.check_setup_libvirt')

        cp = await run(get_virsh_command_args() + ['nodedev-list', 'usb_device'], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve USB devices: {cp.stderr.decode()}')

        devices = [k for k in map(str.strip, cp.stdout.decode().split('\n')) if RE_VALID_USB_DEVICE.findall(k)]
        mapping = {}
        for device in devices:
            details = await self.usb_passthrough_device(device)
            if details['error']:
                continue
            mapping[device] = details

        return mapping
