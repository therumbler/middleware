# -*- coding=utf-8 -*-
import concurrent.futures
import functools
import logging
import os
import subprocess

from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["run_command_with_user_context", "run_with_user_context", "set_user_context"]


def set_user_context(user_details: dict) -> None:
    os.setgroups(user_details['grouplist'], user_details['pw_uid'])
    os.setresgid(user_details['pw_gid'], user_details['pw_gid'], user_details['pw_gid'])
    os.setresuid(user_details['pw_uid'], user_details['pw_uid'], user_details['pw_uid'])

    if any(
        c() != v for c, v in (
            (os.getuid, user_details['pw_uid']),
            (os.geteuid, user_details['pw_uid']),
            (os.getgid, user_details['pw_gid']),
            (os.getegid, user_details['pw_gid']),
        )
    ):
        raise Exception(f"Unable to set user context to {user_details['pw_name']!r} user")

    try:
        os.chdir(user_details['pw_dir'])
    except Exception:
        os.chdir("/var/empty")

    os.environ.update({
        "HOME": user_details['pw_dir'],
        "PATH": "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin",
    })


def run_with_user_context(func: Callable, user: dict, func_args: Optional[list] = None) -> Any:
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1, initializer=functools.partial(set_user_context, user)
    ) as exc:
        return exc.submit(func, *(func_args or [])).result()


def run_command_with_user_context(commandline: str, user: str, callback: Callable) -> subprocess.CompletedProcess:
    p = subprocess.Popen(["sudo", "-H", "-u", user, "sh", "-c", commandline],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stdout = b""
    while True:
        line = p.stdout.readline()
        if not line:
            break

        stdout += line
        callback(line)

    p.communicate()

    return subprocess.CompletedProcess(commandline, stdout=stdout, returncode=p.returncode)
