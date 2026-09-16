#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import datetime as dt
import os
import pathlib
import socket
import socketserver
import subprocess
import threading

ROOT = pathlib.Path(os.environ.get("ES_TEST_SERVER_ROOT", "/tmp/es-protocols"))
LOG = pathlib.Path(os.environ.get("ES_TEST_SERVER_LOG", "/tmp/es-protocol-logs"))
ROOT.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)

for name in ("ftp", "sftp", "webdav"):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

procs: list[subprocess.Popen] = []
_open_logs = []

def start_process(cmd: list[str], logname: str) -> None:
    out = open(LOG / logname, "wb")
    _open_logs.append(out)
    procs.append(subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT))


# ---------------------------------------------------------------------------
# Dependency-free FTP fixture on 2121.
# It intentionally implements the common subset ES needs for connect/list/read/write/delete.
# Binding is performed synchronously before any distro vsftpd process can race for the port.
# ---------------------------------------------------------------------------
FTP_ROOT = (ROOT / "ftp").resolve()

class _FTPHandler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.cwd = pathlib.PurePosixPath("/")
        self.pasv: socket.socket | None = None
        self.rename_from: pathlib.Path | None = None
        self.rest = 0
        self.authed = False

    def log(self, text: str) -> None:
        with open(LOG / "ftp.log", "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def reply(self, code: int, text: str) -> None:
        self.wfile.write(f"{code} {text}\r\n".encode())
        self.wfile.flush()

    def safe_path(self, arg: str = "") -> pathlib.Path:
        arg = arg.strip() or "."
        if arg.startswith("/"):
            rel = pathlib.PurePosixPath(arg)
        else:
            rel = self.cwd / arg
        parts=[]
        for p in rel.parts:
            if p in ("/", "", "."):
                continue
            if p == "..":
                if parts: parts.pop()
            else:
                parts.append(p)
        p = FTP_ROOT.joinpath(*parts).resolve()
        if p != FTP_ROOT and FTP_ROOT not in p.parents:
            raise PermissionError("path escape")
        return p

    def display_path(self, p: pathlib.Path) -> str:
        rel = p.relative_to(FTP_ROOT)
        return "/" if str(rel) == "." else "/" + rel.as_posix()

    def close_pasv(self):
        if self.pasv is not None:
            try: self.pasv.close()
            except Exception: pass
            self.pasv = None

    def open_pasv(self):
        self.close_pasv()
        s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", 0))
        s.listen(1)
        s.settimeout(12)
        self.pasv=s
        return s.getsockname()[1]

    def data_conn(self):
        if self.pasv is None:
            self.reply(425, "Use PASV or EPSV first")
            return None
        self.reply(150, "Opening data connection")
        try:
            conn,_=self.pasv.accept()
            conn.settimeout(12)
            return conn
        except Exception:
            self.reply(425, "Cannot open data connection")
            return None
        finally:
            self.close_pasv()

    def list_line(self, p: pathlib.Path) -> str:
        st=p.stat()
        mode="d" if p.is_dir() else "-"
        when=dt.datetime.fromtimestamp(st.st_mtime).strftime("%b %d %H:%M")
        return f"{mode}rw-r--r-- 1 esuser esuser {st.st_size:>10} {when} {p.name}\r\n"

    def handle(self):
        self.reply(220, "ES disposable privacy-audit FTP")
        self.log(f"control connect {self.client_address[0]}:{self.client_address[1]}")
        while True:
            raw=self.rfile.readline(8192)
            if not raw: break
            line=raw.decode("utf-8","replace").rstrip("\r\n")
            if not line: continue
            cmd,_,arg=line.partition(" ")
            cmd=cmd.upper(); arg=arg.strip()
            self.log(f"C> {cmd} {'***' if cmd=='PASS' else arg}")
            try:
                if cmd == "USER":
                    self.reply(331, "Password required")
                elif cmd == "PASS":
                    if arg == "espass": self.authed=True; self.reply(230, "Logged on")
                    else: self.reply(530, "Login incorrect")
                elif cmd == "SYST": self.reply(215, "UNIX Type: L8")
                elif cmd == "OPTS": self.reply(200, "UTF8 enabled")
                elif cmd == "CLNT": self.reply(200, "Client noted")
                elif cmd == "FEAT":
                    self.wfile.write(b"211-Features\r\n UTF8\r\n EPSV\r\n PASV\r\n SIZE\r\n MDTM\r\n MLST type*;size*;modify*;\r\n211 End\r\n"); self.wfile.flush()
                elif cmd == "NOOP": self.reply(200, "OK")
                elif cmd == "TYPE": self.reply(200, "Type set")
                elif cmd == "PWD": self.reply(257, f'"{self.cwd.as_posix()}" is current directory')
                elif cmd == "CWD":
                    p=self.safe_path(arg)
                    if p.is_dir(): self.cwd=pathlib.PurePosixPath(self.display_path(p)); self.reply(250,"Directory changed")
                    else: self.reply(550,"Not a directory")
                elif cmd == "CDUP":
                    p=self.safe_path("..")
                    self.cwd=pathlib.PurePosixPath(self.display_path(p)); self.reply(250,"Directory changed")
                elif cmd == "PASV":
                    port=self.open_pasv(); p1,p2=divmod(port,256)
                    self.reply(227, f"Entering Passive Mode (10,0,2,2,{p1},{p2})")
                elif cmd == "EPSV":
                    port=self.open_pasv(); self.reply(229, f"Entering Extended Passive Mode (|||{port}|)")
                elif cmd in ("LIST","NLST","MLSD"):
                    p=self.safe_path(arg.split()[-1] if arg and not arg.startswith("-") else ".")
                    items=list(p.iterdir()) if p.is_dir() else [p]
                    conn=self.data_conn()
                    if conn:
                        with conn:
                            for item in sorted(items, key=lambda x:x.name):
                                if cmd == "NLST": out=item.name+"\r\n"
                                elif cmd == "MLSD":
                                    st=item.stat(); typ="dir" if item.is_dir() else "file"; mod=dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y%m%d%H%M%S")
                                    out=f"type={typ};size={st.st_size};modify={mod}; {item.name}\r\n"
                                else: out=self.list_line(item)
                                conn.sendall(out.encode("utf-8"))
                        self.reply(226,"Transfer complete")
                elif cmd == "SIZE": self.reply(213, str(self.safe_path(arg).stat().st_size))
                elif cmd == "MDTM":
                    stamp=dt.datetime.fromtimestamp(self.safe_path(arg).stat().st_mtime).strftime("%Y%m%d%H%M%S")
                    self.reply(213, stamp)
                elif cmd == "REST": self.rest=int(arg or "0"); self.reply(350,"Restart position accepted")
                elif cmd == "RETR":
                    p=self.safe_path(arg); conn=self.data_conn()
                    if conn:
                        with conn, open(p,"rb") as f:
                            if self.rest: f.seek(self.rest)
                            while True:
                                b=f.read(65536)
                                if not b: break
                                conn.sendall(b)
                        self.rest=0; self.reply(226,"Transfer complete")
                elif cmd in ("STOR","APPE"):
                    p=self.safe_path(arg); p.parent.mkdir(parents=True,exist_ok=True); conn=self.data_conn()
                    if conn:
                        with conn, open(p,"ab" if cmd=="APPE" else "wb") as f:
                            while True:
                                b=conn.recv(65536)
                                if not b: break
                                f.write(b)
                        self.reply(226,"Transfer complete")
                elif cmd == "DELE": self.safe_path(arg).unlink(); self.reply(250,"Deleted")
                elif cmd == "MKD": p=self.safe_path(arg); p.mkdir(parents=True,exist_ok=True); self.reply(257,f'"{self.display_path(p)}" created')
                elif cmd == "RMD": self.safe_path(arg).rmdir(); self.reply(250,"Removed")
                elif cmd == "RNFR": self.rename_from=self.safe_path(arg); self.reply(350,"Ready for destination")
                elif cmd == "RNTO":
                    if self.rename_from is None: self.reply(503,"RNFR required")
                    else: self.rename_from.rename(self.safe_path(arg)); self.rename_from=None; self.reply(250,"Renamed")
                elif cmd == "QUIT": self.reply(221,"Bye"); break
                else: self.reply(502,"Command not implemented")
            except FileNotFoundError: self.reply(550,"Not found")
            except PermissionError: self.reply(550,"Permission denied")
            except Exception as exc:
                self.log(f"ERR {cmd}: {type(exc).__name__}: {exc}")
                self.reply(451,"Local error")
        self.close_pasv()

class _ThreadingFTP(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True

ftp_server=_ThreadingFTP(("0.0.0.0",2121),_FTPHandler)
(LOG / "ftp.log").write_text("FTP listening on 2121 (stdlib fixture)\n", encoding="utf-8")
threading.Thread(target=ftp_server.serve_forever, name="es-audit-ftp", daemon=True).start()


# WebDAV on 8080.
start_process([
    "wsgidav", "--host=0.0.0.0", "--port=8080", "--root", str(ROOT / "webdav"),
    "--auth=anonymous"
], "webdav.log")

(LOG / "smb.log").write_text("SMB is provided by system smbd on port 445\n", encoding="utf-8")

# SFTP on 2222.
async def sftp_main() -> None:
    import asyncssh

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username): return True
        def password_auth_supported(self): return True
        def validate_password(self, username, password): return username == "esuser" and password == "espass"

    host_key = asyncssh.generate_private_key("ssh-rsa")
    await asyncssh.create_server(
        Server, "0.0.0.0", 2222, server_host_keys=[host_key],
        sftp_factory=lambda chan: asyncssh.SFTPServer(chan, chroot=str(ROOT / "sftp")),
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
