#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
import pathlib
import subprocess
import threading

ROOT = pathlib.Path(os.environ.get("ES_TEST_SERVER_ROOT", "/tmp/es-protocols"))
LOG = pathlib.Path(os.environ.get("ES_TEST_SERVER_LOG", "/tmp/es-protocol-logs"))
ROOT.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)

# The workflow creates all fixture files before this process starts. Do not rewrite them here: FTP
# and SMB fixture directories are intentionally chowned to the disposable login user and racing a
# second write from this unprivileged helper can fail.
for name in ("sftp", "webdav"):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

procs: list[subprocess.Popen] = []
_open_logs = []

def start_process(cmd: list[str], logname: str) -> None:
    out = open(LOG / logname, "wb")
    _open_logs.append(out)
    procs.append(subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT))

# WebDAV on 8080. Anonymous is intentional: this test is about transport and file-system behavior,
# not password storage. ES still has to enumerate/read/write through its WebDAV implementation.
start_process([
    "wsgidav", "--host=0.0.0.0", "--port=8080", "--root", str(ROOT / "webdav"),
    "--auth=anonymous"
], "webdav.log")

# FTP and SMB are provided by system vsftpd/smbd from the workflow.
(LOG / "ftp.log").write_text("FTP is provided by system vsftpd on port 2121\n", encoding="utf-8")
(LOG / "smb.log").write_text("SMB is provided by system smbd on port 445\n", encoding="utf-8")

# SFTP is implemented in-process with asyncssh so no system sshd configuration is required.
async def sftp_main() -> None:
    import asyncssh

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return True

        def password_auth_supported(self):
            return True

        def validate_password(self, username, password):
            return username == "esuser" and password == "espass"

    host_key = asyncssh.generate_private_key("ssh-rsa")
    await asyncssh.create_server(
        Server,
        "0.0.0.0",
        2222,
        server_host_keys=[host_key],
        sftp_factory=lambda chan: asyncssh.SFTPServer(
            chan, chroot=str(ROOT / "sftp")
        ),
    )
    with open(LOG / "sftp.log", "a", encoding="utf-8") as f:
        f.write("SFTP listening on 2222\n")
    await asyncio.Future()

try:
    asyncio.run(sftp_main())
except Exception as exc:
    with open(LOG / "sftp.log", "a", encoding="utf-8") as f:
        f.write(f"SFTP startup/runtime error: {type(exc).__name__}: {exc}\n")
    threading.Event().wait()
