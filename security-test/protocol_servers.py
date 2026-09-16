#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
import pathlib
import subprocess
import threading
from shutil import which

ROOT = pathlib.Path(os.environ.get("ES_TEST_SERVER_ROOT", "/tmp/es-protocols"))
LOG = pathlib.Path(os.environ.get("ES_TEST_SERVER_LOG", "/tmp/es-protocol-logs"))
ROOT.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)
CANARY = "ES_REMOTE_CANARY_7A9C41D3"

for name in ("ftp", "sftp", "webdav", "smb"):
    p = ROOT / name
    p.mkdir(parents=True, exist_ok=True)
    (p / "readme.txt").write_text(f"{CANARY} {name} read test\n", encoding="utf-8")
    (p / ".hidden_remote_test").write_text(f"{CANARY} {name} hidden\n", encoding="utf-8")

procs: list[subprocess.Popen] = []
_open_logs = []

def start_process(cmd: list[str], logname: str, sudo: bool = False) -> None:
    out = open(LOG / logname, "wb")
    _open_logs.append(out)
    if sudo:
        cmd = ["sudo", "-E"] + cmd
    procs.append(subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT))

# FTP is started from pyftpdlib's Python API rather than its CLI. The CLI changed between releases
# and previously exited before the audit began.
def start_ftp() -> None:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    authorizer = DummyAuthorizer()
    authorizer.add_user(
        "esuser", "espass", str(ROOT / "ftp"), perm="elradfmwMT"
    )
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.banner = "ES disposable privacy-audit FTP"
    server = FTPServer(("0.0.0.0", 2121), handler)
    with open(LOG / "ftp.log", "a", encoding="utf-8") as f:
        f.write("FTP listening on 2121\n")
    server.serve_forever(timeout=0.5, blocking=True, handle_exit=False)

threading.Thread(target=start_ftp, name="es-audit-ftp", daemon=True).start()

# WebDAV on 8080. Anonymous is intentional: this test is about transport and file-system behavior,
# not password storage. ES still has to enumerate/read/write through its WebDAV implementation.
start_process([
    "wsgidav", "--host=0.0.0.0", "--port=8080", "--root", str(ROOT / "webdav"),
    "--auth=anonymous"
], "webdav.log")

# SMB on standard port 445 so ES does not need a nonstandard SMB-port parser.
smb_cmd = next((c for c in ("impacket-smbserver", "smbserver.py") if which(c)), None)
if smb_cmd:
    start_process([
        smb_cmd, "SHARE", str(ROOT / "smb"), "-smb2support", "-username", "esuser",
        "-password", "espass", "-port", "445"
    ], "smb.log", sudo=True)
else:
    (LOG / "smb.log").write_text("SMB server command not found\n", encoding="utf-8")

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
    # Keep the parent alive so FTP/WebDAV/SMB logs remain available to the workflow diagnostics.
    threading.Event().wait()
