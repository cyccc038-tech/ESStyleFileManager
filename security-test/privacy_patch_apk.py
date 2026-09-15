#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import shutil
import struct
import sys
import tempfile
import zipfile
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
    raw = host.encode("ascii")
    prefix = b"127.0.0.1/"
    if len(raw) >= len(prefix):
        return prefix + b"x" * (len(raw) - len(prefix))
    return b"x" * len(raw)


def fix_dex_header(data: bytearray) -> None:
    if not data.startswith(b"dex\n"):
        return
    data[12:32] = hashlib.sha1(data[32:]).digest()
    checksum = zlib.adler32(data[12:]) & 0xFFFFFFFF
    data[8:12] = struct.pack("<I", checksum)


def patch_dex(data: bytes) -> tuple[bytes, int, dict[str, int]]:
    out = bytearray(data)
    total = 0
    counts: dict[str, int] = {}
    for host in BLOCKED_HOSTS:
        old = host.encode("ascii")
        new = safe_replacement(host)
        count = out.count(old)
        if count:
            out = bytearray(bytes(out).replace(old, new))
            counts[host] = count
            total += count
    if total:
        fix_dex_header(out)
    return bytes(out), total, counts


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: privacy_patch_apk.py input.apk output-unsigned.apk", file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    if not src.is_file():
        raise SystemExit(f"missing input: {src}")

    grand_total = 0
    all_counts: dict[str, int] = {}
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w", allowZip64=True) as zout:
        for info in zin.infolist():
            # Drop v1 signature material because the output will be signed again with apksigner.
            upper = info.filename.upper()
            if upper.startswith("META-INF/") and (
                upper.endswith(".RSA") or upper.endswith(".DSA") or upper.endswith(".EC")
                or upper.endswith(".SF") or upper == "META-INF/MANIFEST.MF"
            ):
                continue

            data = zin.read(info.filename)
            if info.filename.startswith("classes") and info.filename.endswith(".dex"):
                data, count, counts = patch_dex(data)
                grand_total += count
                for host, n in counts.items():
                    all_counts[host] = all_counts.get(host, 0) + n

            # Preserve original compression choice and metadata. zipalign runs after this step.
            zout.writestr(info, data)

    print(f"patched literals: {grand_total}")
    for host in BLOCKED_HOSTS:
        print(f"{host}: {all_counts.get(host, 0)}")

    # Verify the selected literals no longer occur in any DEX.
    leftovers = []
    with zipfile.ZipFile(dst, "r") as z:
        for name in z.namelist():
            if not (name.startswith("classes") and name.endswith(".dex")):
                continue
            data = z.read(name)
            for host in BLOCKED_HOSTS:
                if host.encode("ascii") in data:
                    leftovers.append((name, host))
    if leftovers:
        raise SystemExit(f"blocked host literals remain: {leftovers}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
