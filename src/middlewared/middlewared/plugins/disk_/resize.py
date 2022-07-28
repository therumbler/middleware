import os
import asyncio
import subprocess

from middlewared.utils import run
from middlewared.service import Service, CallError, private, accepts, returns, job
from middlewared.schema import Dict, Str, Int, List, Bool


class DiskService(Service):

    @private
    async def resize_impl(self, disk):
        cmd = ['disk_resize', disk['name']]
        if disk['size']:
            cmd.append(f'{disk["size"]}G')

        cp = await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        if cp.returncode != 0:
            err = f'DISK: {disk["name"]!r}'
            if disk['size']:
                err += f' SIZE: {disk["size"]} gigabytes'
            err += f' ERROR: {cp.stdout}'

            raise OSError(cp.returncode, os.sterror(cp.returncode), err)

    @accepts(
        List('disks', required=True, items=[
            Dict(
                Str('name', required=True),
                Int('size', required=False, default=None),
            )
        ]),
        Bool('raise_error', default=False)
    )
    @job(lock='disk_resize')
    @returns()
    async def resize(self, job, data, raise_error):
        """
        Takes a list of disks. Each list entry is a dict that requires a key, value pair.
        `name`: string (the name of the disk (i.e. sda))
        `size`: integer (given in gigabytes)
        `raise_error`: boolean
            when true, will raise a `CallError` if any failures occur
            when false, will will log the errors if any failures occur

        NOTE:
            if `size` is given, the disk with `name` will be resized
                to `size` (overprovision).
            if `size` is not given, the disk with `name` will be resized
                to it's original size (unoverprovision).
        """
        # since it's a list of disks, we could have received duplicate
        # key,value pairs so ensure we don't try to run `disk_resize` on
        # the same disk by removing duplicates
        disks = [i for idx, i in enumerate(data) if i not in data[idx + 1]]
        exceptions = await asyncio.gather(*[self.overprovision_impl(disk) for disk in disks], return_exceptions=True)
        failures = []
        for _, exc in filter(lambda x: isinstance(x[1], OSError), zip(disks, exceptions)):
            failures.append(str(exc))

        if failures:
            err = f'Failure resizing: {", ".join(failures)}'
            if raise_error:
                raise CallError(err)
            else:
                self.logger.error(err)
