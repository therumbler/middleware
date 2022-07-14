import subprocess

from bsd.disk import get_size_with_name, get_sectorsize_with_name
from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def format(self, disk, swapgb, sync=True):
        size = get_size_with_name(disk)
        if not size:
            raise CallError(f'Unable to determine size of {disk!r}')
        elif size - 102400 <= swapgb * 1024 * 1024 * 1024:
            # The GPT header takes about 34KB + alignment, round it to 100
            raise CallError(f'Disk size for {disk!r} must be larger than {swapgb}GB')

        job = self.middleware.call_sync('disk.wipe', disk, 'QUICK', sync)
        job.wait_sync()
        if job.error:
            raise CallError(f'Failed to wipe disk {disk}: {job.error}')

        # Calculate swap size.
        swapsize = swapgb * 1024 * 1024 * 1024 / (get_sectorsize_with_name(disk) or 512)
        # Round up to nearest whole integral multiple of 128
        # so next partition starts at mutiple of 128.
        swapsize = (int((swapsize + 127) / 128)) * 128

        commands = [('gpart', 'create', '-s', 'gpt', f'/dev/{disk}')]
        if swapsize > 0:
            commands.extend([
                ('gpart', 'add', '-a', '4k', '-b', '128', '-t', 'freebsd-swap', '-s', str(swapsize), disk),
                ('gpart', 'add', '-a', '4k', '-t', 'freebsd-zfs', disk),
            ])
        else:
            commands.append(('gpart', 'add', '-a', '4k', '-b', '128', '-t', 'freebsd-zfs', disk))

        # Install a dummy boot block so system gives meaningful message if booting
        # from the wrong disk.
        commands.append(('gpart', 'bootcode', '-b', '/boot/pmbr-datadisk', f'/dev/{disk}'))
        for command in commands:
            cp = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )
            if cp.returncode != 0:
                raise CallError(f'Unable to GPT format the disk "{disk}": {cp.stderr}')

        if sync:
            # We might need to sync with reality (e.g. devname -> uuid)
            self.middleware.call_sync('disk.sync', disk).wait()
