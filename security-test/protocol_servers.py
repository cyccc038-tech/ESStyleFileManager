#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
import pathlib
import subprocess
import sys
import time

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

def start(cmd: list[str], logname: str, sudo: bool = False) -> None:
    out = open(LOG / logname, "wb")
    if sudo:
        cmd = ["sudo", "-E"] + cmd
    procs.append(subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT))

# FTP on 2121.
start([
    sys.executable, "-m", "pyftpdlib", "-i", "0.0.0.0", "-p", "2121",
    "-u", "esuser", "-P", "espass", "-d", str(ROOT / "ftp"), "-w"
], "ftp.log")

# WebDAV on 8080. Anonymous is intentional: this test is about transport and file-system behavior,
# not password storage. ES still has to enumerate/read/write through its WebDAV implementation.
start([
    "wsgidav", "--host=0.0.0.0", "--port=8080", "--root", str(ROOT / "webdav"),
    "--auth=anonymous"
], "webdav.log")

# SMB on standard port 445 so ES does not need a nonstandard SMB-port parser.
smb_cmd = None
for candidate in ("impacket-smbserver", "smbserver.py"):
    from shutil import which
    if which(candidate):
        smb_cmd = candidate
        break
if smb_cmd:
    start([
        smb_cmd, "SHARE", str(ROOT / "smb"), "-smb2support", "-username", "esuser",
        "-password", "espass", "-port", "445"
    ], "smb.log", sudo=True)
else:
    (LOG / "smb.log").write_text("SMB server command not found\n", encoding="utf-8")

# SFTP is implemented in-process with asyncssh.
async def sftp_main() -> None:
    import asyncssh

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return True
        def password_auth_supported(self):
            return True
        def validate_password(self, username, password):
            return username == "esuser" and password == "espass"

    key_path = ROOT / "sftp-host-key"
    if not key_path.exists():
        key = asyncssh.generate_private_key("ssh-rsa")
        key.write_private_key_file(str(key_path))

    await asyncssh.create_server(
        Server, "0.0.0.0", 2222,
        server_host_keys=[str(key_path)],
        sftp_factory=lambda chan: asyncssh.SFTPServer(chan, chroot=str(ROOT / "sftp")),
    )
    with open(LOG / "sftp.log", "a", encoding="utf-8") as f:
        f.write("SFTP listening on 2222\n")
        f.flush()
    await asyncio.Future()

asyncio.run(sftp_main())
