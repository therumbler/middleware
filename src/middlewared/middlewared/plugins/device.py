import asyncio
import os
import socket

from middlewared.schema import accepts, Str
from middlewared.service import Service

from bsd import devinfo, geom

DEVD_SOCKETFILE = '/var/run/devd.pipe'


class DeviceService(Service):

    @accepts(Str('type', enum=['SERIAL', 'DISK']))
    async def get_info(self, _type):
        """
        Get info for certain device types.

        Currently only SERIAL is supported.
        """
        return await getattr(self, f'_get_{_type.lower()}')()

    async def _get_serial(self):
        ports = []
        for devices in devinfo.DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                ports.append({
                    'name': dev.name,
                    'description': dev.desc,
                    'drivername': dev.drivername,
                    'location': dev.location,
                    'start': hex(dev.start),
                    'size': dev.size
                })
        return ports

    async def _get_disk(self):
        await self.middleware.run_in_thread(geom.scan)
        disks = {}
        klass = geom.class_by_name('DISK')
        if not klass:
            return disks
        for g in klass.geoms:
            # Skip cd*
            if g.name.startswith('cd'):
                continue
            disk = {
                'name': g.name,
                'mediasize': g.provider.mediasize,
                'sectorsize': g.provider.sectorsize,
                'stripesize': g.provider.stripesize,
            }
            if g.provider.config:
                disk.update(g.provider.config)
            disks[g.name] = disk
        return disks


async def devd_loop(middleware):
    while True:
        try:
            if not os.path.exists(DEVD_SOCKETFILE):
                await asyncio.sleep(1)
                continue
            await devd_listen(middleware)
        except ConnectionRefusedError:
            middleware.logger.warn('devd connection refused, retrying...')
        except OSError:
            middleware.logger.warn('devd pipe error, retrying...', exc_info=True)
        await asyncio.sleep(1)


def parse_devd_message(msg):
    """
    Parse devd messages using "=" char as separator.
    We use the first word before "=" as key and every word minus 1 after "=" as value.
    The caveat is that we cant properly parse messages containing "=" in the value,
    however this seems good enough until kernel/devd can provide structured messages.
    """
    parsed = {}
    parts = msg.strip().split('=')
    for idx in range(len(parts) - 1):
        key = parts[idx].rsplit(' ', 1)[-1]
        value = parts[idx + 1].rsplit(' ', 1)[0].strip()
        parsed[key] = value
    return parsed


async def devd_listen(middleware):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(DEVD_SOCKETFILE)
    reader, writer = await asyncio.open_unix_connection(sock=s)

    while True:
        line = await reader.readline()
        line = line.decode(errors='ignore')
        if line == "":
            break

        if not line.startswith('!'):
            # TODO: its not a complete message, ignore for now
            continue

        try:
            parsed = await middleware.run_in_thread(parse_devd_message, line[1:])
        except Exception:
            middleware.logger.warn(f'Failed to parse devd message: {line}')
            continue

        if 'system' not in parsed:
            continue

        # Lets ignore CAM messages for now
        if parsed['system'] in ('CAM', 'ACPI'):
            continue

        await middleware.call_hook(
            f'devd.{parsed["system"]}'.lower(), data=parsed,
        )


def setup(middleware):
    asyncio.ensure_future(devd_loop(middleware))
