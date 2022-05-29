import asyncio
import re
import pathlib

import async_timeout

try:
    import cam
except ImportError:
    cam = None

from middlewared.common.smart.smartctl import SMARTCTL_POWERMODES
from middlewared.schema import Dict, Int, returns
from middlewared.service import accepts, List, private, Service, Str
from middlewared.utils.asyncio_ import asyncio_map


def get_temperature(stdout):
    # ataprint.cpp

    data = {}
    for s in re.findall(r'^((190|194) .+)', stdout, re.M):
        s = s[0].split()
        try:
            data[s[1]] = int(s[9])
        except (IndexError, ValueError):
            pass
    for k in ['Temperature_Celsius', 'Temperature_Internal', 'Drive_Temperature',
              'Temperature_Case', 'Case_Temperature', 'Airflow_Temperature_Cel']:
        if k in data:
            return data[k]

    reg = re.search(r'194\s+Temperature_Celsius[^\n]*', stdout, re.M)
    if reg:
        return int(reg.group(0).split()[9])

    # nvmeprint.cpp

    reg = re.search(r'Temperature:\s+([0-9]+) Celsius', stdout, re.M)
    if reg:
        return int(reg.group(1))

    reg = re.search(r'Temperature Sensor [0-9]+:\s+([0-9]+) Celsius', stdout, re.M)
    if reg:
        return int(reg.group(1))

    # scsiprint.cpp

    reg = re.search(r'Current Drive Temperature:\s+([0-9]+) C', stdout, re.M)
    if reg:
        return int(reg.group(1))


class DiskService(Service):
    @private
    async def disks_for_temperature_monitoring(self):
        return [
            disk['name']
            for disk in await self.middleware.call(
                'disk.query',
                [
                    ['name', '!=', None],
                    ['togglesmart', '=', True],
                    # Polling for disk temperature does not allow them to go to sleep automatically unless
                    # hddstandby_force is used
                    [
                        'OR', [
                            ['hddstandby', '=', 'ALWAYS ON'],
                            ['hddstandby_force', '=', True],
                        ],
                    ]
                ]
            )
        ]

    @accepts(
        Str('name'),
        Str('powermode', enum=SMARTCTL_POWERMODES, default=SMARTCTL_POWERMODES[0]),
    )
    @returns(Int('temperature', null=True))
    async def temperature(self, name, powermode):
        """
        Returns temperature for device `name` using specified S.M.A.R.T. `powermode`.
        """
        if name.startswith('da'):
            smartctl_args = await self.middleware.call('disk.smartctl_args', name) or []
            if not any(s.startswith('/dev/arcmsr') for s in smartctl_args):
                try:
                    temperature = await self.middleware.run_in_thread(lambda: cam.CamDevice(name).get_temperature())
                    if temperature is not None:
                        return temperature
                except Exception:
                    pass

        output = await self.middleware.call('disk.smartctl', name, ['-a', '-n', powermode.lower()],
                                            {'silent': True})
        if output is None:
            return None

        return get_temperature(output)

    @private
    def read_temps(self):
        disks = {
            i['serial']: i['name'] for i in self.middleware.call_sync('datastore.query', 'storage.disk', [
                ['serial', '!=', ''],
                ['togglesmart', '=', True],
                ['hddstandby', '=', 'ALWAYS ON'],
            ], {'prefix': 'disk_'})
        }
        rv = {}
        for i in pathlib.Path('/var/lib/smartmontools').iterdir():
            # TODO: throw this into multiple threads since we're reading data from disk
            # to make this really go brrrrr (even though it only takes ~0.2 seconds on 439 disk system)
            if i.is_file() and i.suffix == '.csv':
                if serial := next((k for k in disks if i.as_posix().find(k) != -1), None):
                    with open(i.as_posix()) as f:
                        for line in f:
                            # iterate to the last line in the file without loading all of it
                            # into memory since `smartd` could have written 1000's (or more)
                            # of lines to the file
                            pass

                        if (info := line.split('\t')) and next((i.find('temperature') != -1 for i in info), None):
                            temp = info[-1].split(';', 1)[-1].strip().replace(';', '')
                            if temp.isdigit():
                                rv[disks[serial]] = int(temp)
        return rv

    @accepts(
        List('names', items=[Str('name')]),
        Str('powermode', enum=SMARTCTL_POWERMODES, default=SMARTCTL_POWERMODES[0]),
    )
    @returns(Dict('disks_temperatures', additional_attrs=True))
    async def temperatures(self, names, powermode):
        """
        Returns temperatures for a list of devices (runs in parallel).
        See `disk.temperature` documentation for more details.
        """
        if len(names) == 0:
            names = await self.disks_for_temperature_monitoring()

        async def temperature(name):
            try:
                async with async_timeout.timeout(15):
                    return await self.middleware.call('disk.temperature', name, powermode)
            except asyncio.TimeoutError:
                return None

        result = dict(zip(names, await asyncio_map(temperature, names, 8)))

        return result
