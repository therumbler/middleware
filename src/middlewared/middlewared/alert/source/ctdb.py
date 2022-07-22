from datetime import timedelta
from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource, SimpleOneShotAlertClass
from middlewared.alert.schedule import IntervalSchedule

ALLOWED_OFFSET_CLOCK_REALTIME = 120
ALLOWED_OFFSET_NTP = 300000


class CtdbInitFailAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "CTDB service initialization failed"
    text = "CTDB service initialization failed: %(errmsg)s"

    async def delete(self, alerts, query):
        return []


class CtdbClusteredServiceAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "Clustered service start failed"
    text = "Clustered service start failed: %(errmsg)s"

    async def delete(self, alerts, query):
        return []


class ClusteredClockskewAlertClass(AlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "Clustered time consistency check failed"
    text = "%(errmsg)s"


class ClusteredClockOffsetAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self):
        def get_clock_realtime(entry):
            return entry['clock_realtime']

        def get_offset(entry):
            return abs(entry['ntp_peer']['offset'])

        if await self.middleware.call('smb.get_smb_ha_mode') != 'CLUSTERED':
            return

        if not await self.middleware.call('ctdb.general.healthy'):
            return

        if not await self.middleware.call('ctdb.general.is_rec_master'):
            return

        time_job = await self.middleware.call('cluster.utils.time_info')
        rv = await time_job.wait()
        if rv['state'] != 'SUCCESS':
            return

        clock_high = max(rv['result'], key=get_clock_realtime)
        clock_low = min(rv['result'], key=get_clock_realtime)
        current_realtime_offset = clock_high['clock_realtime'] - clock_low['clock_realtime']

        if current_realtime_offset > ALLOWED_OFFSET_CLOCK_REALTIME:
            # We have to have a fudge factor because there may be some seconds delay
            # for all nodes returning their results. 5 minutes is sufficient to break
            # kerberos authentication, and so 2 minutes was selected as the canary.
            high_node = clock_high['pnn']
            low_node = clock_low['pnn']

            errmsg = (
                f'Time offset of {current_realtime_offset} between nodes {high_node} '
                f'and {low_node} exceeds {ALLOWED_OFFSET_CLOCK_REALTIME} seconds'
            )

            return Alert(
                ClusteredClockOffsetAlertSource,
                {'verrs': errmsg},
                key=None
            )

        worst_offset = max(rv['result'], key=get_offset)
        if abs(worst_offset['ntp_peer']['offset']) > ALLOWED_OFFSET_NTP:
            errmsg = f'NTP offset of node {worst_offset["pnn"]} exceeds 5 minutes.'
            return Alert(
                ClusteredClockOffsetAlertSource,
                {'verrs': errmsg},
                key=None
            )
