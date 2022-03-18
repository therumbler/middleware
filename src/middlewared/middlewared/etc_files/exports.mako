<%
    from pathlib import Path

    map_ids = {
        'maproot_user': -1,
        'maproot_group': -1,
        'mapall_user': -1,
        'mapall_group': -1,
    }

    def do_map(share, map_type):
        output = []
        if share[f'{map_type}_user']:
            uid = middleware.call_sync(
                'user.get_user_obj',
                {'username': share[f'{map_type}_user']}
            )['pw_uid']
            map_ids[f'{map_type}_user'] = uid
            output.append(f'anonuid={uid}')

        if share[f'{map_type}_group']:
            gid = middleware.call_sync(
                'group.get_group_obj',
                {'groupname': share[f'{map_type}_group']}
            )['gr_gid']
            map_ids[f'{map_type}_group'] = gid
            output.append(f'anongid={gid}')

        return output

    def generate_options(share, global_sec, config):
        params = []

        all_squash = False
        if share["security"]:
            sec = f'sec={":".join(share["security"])}'
            params.append(sec.lower())
        else:
            sec = f'sec={":".join(global_sec)}'
            params.append(sec)

        if not share["ro"]:
            params.append("rw")

        try:
            mapall = do_map(share, "mapall")
        except KeyError:
            middleware.logger.warning(
                "NSS lookup for anonymous account failed. "
                "disabling NFS exports.",
                exc_info = True
            )
            raise FileShouldNotExist()

        if mapall:
            params.extend(mapall)
            params.append("all_squash")

        try:
            maproot = do_map(share, "maproot")
        except KeyError:
            middleware.logger.warning(
                "NSS lookup for anonymous account failed. "
                "disabling NFS exports.",
                exc_info = True
            )
            raise FileShouldNotExist()

        if maproot:
            params.extend(maproot)

        if map_ids['maproot_user'] == 0 and map_ids['maproot_group'] == 0:
            params.append('no_root_squash')

        if config['allow_nonroot']:
            params.append("insecure")

        return ','.join(params)

    entries = []
    config = render_ctx["nfs.config"]
    shares = render_ctx["sharing.nfs.query"]
    if not shares:
        raise FileShouldNotExist()

    has_nfs_principal = middleware.call_sync('kerberos.keytab.has_nfs_principal')
    global_sec = middleware.call_sync("nfs.sec", config, has_nfs_principal) or ["sys"]

    for share in shares:
        opts = generate_options(share, global_sec, config)
        for path in share["paths"]:
            p = Path(path)
            if not p.exists():
                middleware.logger.debug("%s: path does not exist, omitting from NFS exports", path)
                continue

            anonymous = True
            options = []
            params = opts
            params += ",no_subtree_check" if p.is_mount() else ",subtree_check"

            for host in share["hosts"]:
                options.append(f'{host}({params})')
                anonymous = False

            for network in share["networks"]:
                options.append(f'{network}({params})')
                anonymous = False

            if anonymous:
                options.append(f'*({params})')

            entries.append({"path": path, "options": options})

    if not entries:
        raise FileShouldNotExist()
%>
% for export in entries:
"${export["path"]}"${"\\\n\t"}${"\\\n\t".join(export["options"])}
% endfor
