<% from middlewared.utils import filter_list %>\
% for user in filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']}):
<%
if IS_FREEBSD:
    if user['password_disabled']:
        passwd = "*"
    elif user['locked']:
        passwd = "*LOCKED*"
    else:
        passwd = user['unixhash']
else:
    passwd = "x"

if IS_FREEBSD:
    freebsd_fields = ":0:0:"
else:
    freebsd_fields = ""
%>\
${user['username']}:${passwd}:${user['uid']}:${user['group']['bsdgrp_gid']}:${freebsd_fields}${user['full_name']}:${user['home']}:${user['shell']}
% endfor
% if IS_FREEBSD and middleware.call_sync('nis.config')['enable']:

+:::::::::\
% endif

