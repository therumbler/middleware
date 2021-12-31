import concurrent.futures
import functools
import os
import pwd
import grp
import errno
from typing import Union, Tuple, Optional

from middlewared.service import private, Service, job
from middlewared.service_exception import CallError


def convert_user(pw_obj, getgroups: bool) -> dict:
    if type(pw_obj) != pwd.struct_passwd:
        raise TypeError("pw_obj not struct_passwd")

    user_obj = {
        'pw_name': pw_obj.pw_name,
        'pw_uid': pw_obj.pw_uid,
        'pw_gid': pw_obj.pw_gid,
        'pw_gecos': pw_obj.pw_gecos,
        'pw_dir': pw_obj.pw_dir,
        'pw_shell': pw_obj.pw_shell,
    }
    if getgroups:
        user_obj['grouplist'] = os.getgrouplist(pw_obj.pw_name, pw_obj.pw_gid)

    return user_obj

def convert_group(gr_obj) -> dict:
    if type(gr_obj) != grp.struct_group:
        raise TypeError("gr_obj not struct_group")

    return {
        'gr_name': gr_obj.gr_name,
        'gr_gid': gr_obj.gr_gid,
        'gr_mem': gr_obj.gr_mem
    }

def get_user_list(getgroups: bool) -> list:
    res = []
    for u in pwd.getpwall():
       res.append(convert_user(u, getgroups))

    return res

def get_group_list() -> list:
    res = []
    for g in grp.getgrall():
        res.append(convert_group(g))

    return res

def get_user(request: Tuple[Union[str, int], bool, bool]) -> dict:
    principal, getgroups, ignore_missing = request

    ptype = type(principal)
    if ptype not in (str, int):
        raise TypeError(f'{ptype.__name__}: invalid type')

    try:
        u = pwd.getpwnam(principal) if ptype == str else pwd.getpwuid(principal)
    except KeyError as e:
        if ignore_missing:
            return None

        raise CallError(e.args[0], errno.ENOENT)

    return convert_user(u, getgroups)

def get_group(request: Tuple[Union[str, int], bool]) -> dict:
    principal, ignore_missing = request

    ptype = type(principal)
    if ptype not in (str, int):
        raise TypeError(f'{ptype.__name__}: invalid type')

    try:
        g = grp.getgrnam(principal) if ptype == str else grp.getgrgid(principal)
    except KeyError as e:
        if ignore_missing:
            return None

        raise CallError(e.args[0], errno.ENOENT)

    return convert_group(g)

def nss_lookup_internal(
    nss_type: str,
    principals: list,
    getgroups: Optional[bool] = None,
    ignore_missing: Optional[bool] = False,
    timeout: Optional[Union[float, int]] = None
) -> dict:
    func = None
    payload = None
    res = {}
    if nss_type not in ('USER', 'GROUP', 'USERLIST', 'GROUPLIST'):
        raise ValueError(f'{nss_type}: invald NSS type')

    if nss_type == 'USER':
        func = get_user
        payload = [(x, getgroups, ignore_missing) for x in principals]
    elif nss_type == 'GROUP':
        func = get_group
        payload = [(x, ignore_missing) for x in principals]
    elif nss_type == 'USERLIST':
        payload = (get_user_list, getgroups)
    elif nss_type == 'GROUPLIST':
        payload = (get_group_list,)

    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as exc:
        if nss_type in ('USER', 'GROUP'):
            res = {x: y for x, y in zip(principals, exc.map(func, payload))}
        else:
            res = exc.submit(*payload).result()

    return res


class IdmapService(Service):

    @private
    @job(transient=True)
    def nss_lookup(self, job, data, timeout):
        """
        record type == USER or GROUP
        (getpwname, getpwuid, getgrnam, getgrgid)
        - returns dict (principal requested: result)
        - Can request multiple users / groups at once (but only single record type).
        - If ignore_missing is specified, then value will be None type on KeyError.

        record type == USERLIST or GROUPLIST
        (getpwent, getgrent)
        - returns list of user or group entries.
        """
        return nss_lookup_internal(
            data['record_type'],
            data.get('principals'),
            data.get('get_groups'),
            data.get('ignore_missing', False),
            timeout
        )
