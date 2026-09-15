#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: legacy_compat.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"
build = app / "build.gradle"
text = build.read_text(encoding="utf-8")
for old, new in [
    ("targetSdk 34", "targetSdk 29"),
    ("versionCode 10001", "versionCode 10002"),
    ("versionName '1.7.4-esstyle.1'", "versionName '1.7.4-esstyle.2'"),
]:
    if old not in text:
        raise RuntimeError(f"Expected build.gradle text not found: {old}")
    text = text.replace(old, new, 1)
build.write_text(text, encoding="utf-8")

home = app / "src/main/java/me/zhanghai/android/files/esstyle/EsHomeActivity.kt"
text = home.read_text(encoding="utf-8")
old = '''        root.addView(actionRow("Android / data", "无 Root：通过系统文档授权访问；授权后会加入侧栏") {
            grantAndroidTree("data")
        })
        root.addView(actionRow("Android / obb", "无 Root：通过系统文档授权访问；授权后会加入侧栏") {
            grantAndroidTree("obb")
        })'''
new = '''        root.addView(actionRow("Android / data", "无 Root 兼容模式：优先直接访问；若系统拦截可使用下方授权备用") {
            openAndroidSpecial("data")
        })
        root.addView(actionRow("Android / data 授权备用", "调用系统文档树授权；是否允许由 Android / 厂商 DocumentsUI 决定") {
            grantAndroidTree("data")
        })
        root.addView(actionRow("Android / obb", "无 Root 兼容模式：优先直接访问；若系统拦截可使用下方授权备用") {
            openAndroidSpecial("obb")
        })
        root.addView(actionRow("Android / obb 授权备用", "调用系统文档树授权；是否允许由 Android / 厂商 DocumentsUI 决定") {
            grantAndroidTree("obb")
        })'''
if old not in text:
    raise RuntimeError("Could not locate Android/data home rows")
text = text.replace(old, new, 1)

anchor = '''    private fun grantAndroidTree(target: String) {
        startActivity(Intent(this, EsDocumentTreeGrantActivity::class.java).putExtra("target", target))
    }
'''
insert = '''    private fun openAndroidSpecial(target: String) {
        runCatching {
            val base = Environment.getExternalStorageDirectory().absolutePath
            val path = Paths.get(base, "Android", target)
            startActivity(FileListActivity.createViewIntent(path))
        }.onFailure {
            Toast.makeText(
                this,
                "直接访问失败，尝试使用系统目录授权",
                Toast.LENGTH_LONG
            ).show()
            grantAndroidTree(target)
        }
    }

'''
if anchor not in text:
    raise RuntimeError("Could not locate grantAndroidTree()")
text = text.replace(anchor, insert + anchor, 1)
home.write_text(text, encoding="utf-8")

print("Applied targetSdk 29 legacy-storage compatibility + direct Android/data/obb entry")
