import concurrent.futures
import functools
import os
import pwd
import grp
from typing import Union

from middlewared.service import private, Service


def get_user(request: Tuple[Union[str, int], bool]) -> dict:
    principal, getgroups = request

    ptype = type(principal)
    if ptype not in (str, int):
        raise TypeError(f'{ptype).__name__'}: invalid type)

    u = pwd.getpwnam(principal) if ptype == str else pwd.getpwuid(principal)

    user_obj = {
        'pw_name': u.pw_name,
        'pw_uid': u.pw_uid,
        'pw_gid': u.pw_gid,
        'pw_gecos': u.pw_gecos,
        'pw_dir': u.pw_dir,
        'pw_shell': u.pw_shell,
    }
    if getgroups:
        user_obj['grouplist'] = os.getgrouplist(u.pw_name, u.pw_gid)

    return user_obj


def get_group(principal: Union[str, int]) -> dict:
    if type(principal) not in (str, int):
        raise TypeError(f'{type(principal).__name__}: invalid type)

    if type(principal) == str:
        g = grp.getgrnam(principal)
    else:
        g = grp.getgrgid(principal)

    return {
        'gr_name': g.gr_name,
        'gr_gid': g.gr_gid,
        'gr_mem': g.gr_mem
    }

def nss_lookup_internal(
    nss_type: str,
    principals: list,
    getgroups: Optional[bool] = None,
    timeout: Optional[Union[float, int]] = None
) -> dict:
    func = None
    res = {}

    if nss_type not in ('USER', 'GROUP'):
        raise ValueError(f'{nss_type}: invald NSS type')

    if nss_type == 'USER':
        func = get_user
        payload = [(x, getgroups) for x in principals]

    else:
        payload = principals

    with concurrent.futures.ProcessPoolExecutor() as exc:
        res = {x: y for x, y in zip(principals, exc.map(func, payload))}

    return res


class UserService(Service):

    @private
    @job(transient=True)
    def nss_lookup(self, job, data, timeout):
        return nss_lookup_internal(data['record_type'], data['principals'], data['getgroups'], timeout)
