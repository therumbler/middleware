from middlewared.schema import Dict, Str

from .device import Device
from .utils import create_element


class USB(Device):

    schema = Dict(
        'attributes',
        Str('device', required=True, empty=False),
    )

    @property
    def usb_device(self):
        return self.data['attributes']['device']

    def identity(self):
        return self.usb_device

    def get_vms_using_device(self):
        devs = self.middleware.call_sync(
            'vm.device.query', [['attributes.device', '=', self.usb_device], ['dtype', '=', 'USB']]
        )
        return self.middleware.call_sync('vm.query', [['id', 'in', [dev['vm'] for dev in devs]]])

    def get_details(self):
        return self.middleware.call_sync('vm.device.usb_passthrough_device', self.usb_device)

    def is_available(self):
        return self.get_details()['available']

    def xml_linux(self, *args, **kwargs):
        details = self.get_details()['capability']
        device_xml = create_element(
            'hostdev', mode='subsystem', type='usb', managed='yes', attribute_dict={
                'children': [
                    create_element('source', attribute_dict={'children': [
                        create_element('vendor', id=details['vendor_id']),
                        create_element('product', id=details['product_id']),
                        create_element('address', bus=details['bus'], device=details['device']),
                    ]}),
                ]
            }
        )
        return device_xml

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        usb_device = device['attributes']['device']
        device_details = self.middleware.call_sync('vm.device.usb_passthrough_device', usb_device)
        if device_details.get('error'):
            verrors.add(
                'attribute.device',
                f'Not a valid choice. The device is not available for USB passthrough: {device_details["error"]}'
            )
