#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct
import sys
import zlib
from pathlib import Path

BLOCKED_HOSTS = [
    "stat.doglobal.net",
    "errnewlog.umeng.com",
    "errnewlogos.umeng.com",
    "cnlogs.umeng.com",
    "aspect-upush.umeng.com",
    "utoken.umeng.com",
    "ucc.umeng.com",
    "astat.bugly.qcloud.com",
    "astat.bugly.cros.wr.pvp.net",
    "applog.snssdk.com",
    "log.snssdk.com",
    "rtapplog.snssdk.com",
    "rtlog.snssdk.com",
    "tobapplog.ctobsnssdk.com",
    "toblog.ctobsnssdk.com",
    "scc.bytedance.com",
    "sf3-fe-tos.pglstatp-toutiao.com",
    "cdn-tos-cn.bytedance.net",
    "apps.bytesfield.com",
    "apps.bytesfield-b.com",
    "sf1-amtos-cdn.bytesmanager.com",
    "open.e.kuaishou.com",
    "p1-lm.adkwai.com",
    "p2-lm.adkwai.com",
    "p3-lm.adkwai.com",
    "p4-lm.adkwai.com",
    "p5-lm.adkwai.com",
    "stg-data.ads.heytapmobi.com",
    "adsfs.heytapimage.com",
    "mdp-usertrace-cn.heytapmobi.com",
    "api-audit.heytapmobi.com",
    "adx-data.yfanads.com",
    "api.yfanads.com",
    "log.yfanads.com",
    "tracker.yfanads.com",
    "nsclick.baidu.com",
    "loggw-exsdk.alipay.com",
]


def safe_replacement(host: str) -> bytes:
    # Preserve byte length and almost the entire lexical prefix so DEX string_ids ordering remains
    # valid. Replacing only the final byte makes the hostname invalid while keeping its sort region.
    b = host.encode("ascii")
    return b[:-1] + (b"-" if b[-1:] != b"-" else b"_")


def fix_dex_header(data: bytearray) -> None:
    data[12:32] = hashlib.sha1(data[32:]).digest()
    data[8:12] = struct.pack("<I", zlib.adler32(data[12:]) & 0xFFFFFFFF)


def patch(path: Path) -> int:
    data = bytearray(path.read_bytes())
    if not data.startswith(b"dex\n"):
        raise RuntimeError(f"not dex: {path}")
    total = 0
    for host in BLOCKED_HOSTS:
        old = host.encode("ascii")
        new = safe_replacement(host)
        n = bytes(data).count(old)
        if n:
            data = bytearray(bytes(data).replace(old, new))
            print(f"{path.name}: {host}: {n}")
            total += n
    if total:
        fix_dex_header(data)
        path.write_bytes(data)
    return total


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: patch_dex_only.py classes.dex [classes2.dex ...]", file=sys.stderr)
        return 2
    total = sum(patch(Path(p)) for p in sys.argv[1:])
    print(f"patched literals total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
