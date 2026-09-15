#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: v05_intercept.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"

# v0.5
build = app / "build.gradle"
text = build.read_text(encoding="utf-8")
for old, new in [
    ("versionCode 10004", "versionCode 10005"),
    ("versionName '1.7.4-esstyle.4'", "versionName '1.7.4-esstyle.5'"),
]:
    if old not in text:
        raise RuntimeError(f"Expected version marker not found: {old}")
    text = text.replace(old, new, 1)
build.write_text(text, encoding="utf-8")

# IMPORTANT: The previous build only intercepted the ES-style home shortcut. If the user browsed
# Internal storage -> Android -> data from Material Files itself, Material Files still attempted a
# raw java.nio opendir() and displayed AccessDeniedException. Intercept navigation globally.
fragment = app / "src/main/java/me/zhanghai/android/files/filelist/FileListFragment.kt"
f = fragment.read_text(encoding="utf-8")

import_anchor = "import me.zhanghai.android.files.filejob.FileJobService\n"
if "import me.zhanghai.android.files.esstyle.EsAndroidDataActivity\n" not in f:
    if import_anchor not in f:
        raise RuntimeError("Could not locate FileListFragment import anchor")
    f = f.replace(
        import_anchor,
        "import me.zhanghai.android.files.esstyle.EsAndroidDataActivity\n" + import_anchor,
        1,
    )

navigate_old = '''    override fun navigateTo(path: Path) {
        collapseSearchView()
        val state = layoutManager.onSaveInstanceState()
        viewModel.navigateTo(state!!, path)
    }'''
navigate_new = '''    private fun esAndroidSpecialTarget(path: Path): String? {
        val value = path.toString().replace('\\\\', '/').trimEnd('/')
        return when {
            value.endsWith("/Android/data", ignoreCase = true) -> "data"
            value.endsWith("/Android/obb", ignoreCase = true) -> "obb"
            else -> null
        }
    }

    private fun openEsAndroidSpecial(path: Path): Boolean {
        val target = esAndroidSpecialTarget(path) ?: return false
        startActivity(
            Intent(requireContext(), EsAndroidDataActivity::class.java)
                .putExtra(EsAndroidDataActivity.EXTRA_TARGET, target)
        )
        return true
    }

    override fun navigateTo(path: Path) {
        // Do not ever send Android/data or Android/obb to the raw Linux provider. Android 11+
        // rejects opendir() there even with MANAGE_EXTERNAL_STORAGE. Route to the ES-style
        // per-package SAF browser instead.
        if (openEsAndroidSpecial(path)) return
        collapseSearchView()
        val state = layoutManager.onSaveInstanceState()
        viewModel.navigateTo(state!!, path)
    }'''
if navigate_old not in f:
    raise RuntimeError("Could not locate FileListFragment.navigateTo()")
f = f.replace(navigate_old, navigate_new, 1)

current_old = '''    private fun onCurrentPathChanged(path: Path) {
        updateOverlayToolbar()
        updateBottomToolbar()'''
current_new = '''    private fun onCurrentPathChanged(path: Path) {
        // Also recover from a restored Activity/ViewModel that was already sitting on Android/data
        // from an older test build. Move the underlying file list back to Android and open the
        // synthetic ES browser so upgrading the APK fixes the stale error screen automatically.
        val specialTarget = esAndroidSpecialTarget(path)
        if (specialTarget != null) {
            val safeParent = path.parent ?: Settings.FILE_LIST_DEFAULT_DIRECTORY.valueCompat
            viewModel.resetTo(safeParent)
            startActivity(
                Intent(requireContext(), EsAndroidDataActivity::class.java)
                    .putExtra(EsAndroidDataActivity.EXTRA_TARGET, specialTarget)
            )
            return
        }
        updateOverlayToolbar()
        updateBottomToolbar()'''
if current_old not in f:
    raise RuntimeError("Could not locate FileListFragment.onCurrentPathChanged()")
f = f.replace(current_old, current_new, 1)
fragment.write_text(f, encoding="utf-8")

# Make the Android/data screen self-explanatory on Xiaomi/HyperOS. The screenshots from Xiaomi 13
# show the user landed on the top-level Accessibility page; the actual ESStyle service lives under
# “已下载的应用”. Also provide app-details access for Android 13+ restricted-settings handling.
data_activity = app / "src/main/java/me/zhanghai/android/files/esstyle/EsAndroidDataActivity.kt"
d = data_activity.read_text(encoding="utf-8")
if "import android.net.Uri\n" not in d:
    d = d.replace("import android.graphics.Color\n", "import android.graphics.Color\nimport android.net.Uri\n", 1)

old_buttons = '''        root.addView(Button(this).apply {
            text = "自动授权全部应用目录"
            setOnClickListener { startBatchGrant() }
        })

        root.addView(Button(this).apply {
            text = "打开无障碍设置"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })'''
new_buttons = '''        root.addView(TextView(this).apply {
            text = if (isAccessibilityServiceEnabled()) {
                "自动目录授权服务：已开启"
            } else {
                "自动目录授权服务：未开启。Xiaomi/HyperOS：点下面按钮后，再点“已下载的应用” → “ESStyle 文件管理器” → 开启。"
            }
            textSize = 14f
            setTextColor(if (isAccessibilityServiceEnabled()) Color.rgb(35, 140, 65) else Color.rgb(190, 80, 45))
            setPadding(0, 0, 0, dp(8))
        })

        root.addView(Button(this).apply {
            text = "1. 打开无障碍设置（进入“已下载的应用”）"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })

        root.addView(Button(this).apply {
            text = "如果系统提示“受限设置”，打开应用详情"
            setOnClickListener {
                startActivity(
                    Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = Uri.parse("package:$packageName")
                    }
                )
            }
        })

        root.addView(Button(this).apply {
            text = "2. 开始自动授权全部应用目录"
            setOnClickListener { startBatchGrant() }
        })'''
if old_buttons not in d:
    raise RuntimeError("Could not locate Android/data activity buttons")
d = d.replace(old_buttons, new_buttons, 1)
data_activity.write_text(d, encoding="utf-8")

# Make the accessibility entry easier to identify in Xiaomi's downloaded-apps list.
manifest = app / "src/main/AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")
m = m.replace(
    'android:name="me.zhanghai.android.files.esstyle.EsAutoAuthService"\n            android:exported="true"\n            android:label="@string/app_name"',
    'android:name="me.zhanghai.android.files.esstyle.EsAutoAuthService"\n            android:exported="true"\n            android:label="ESStyle 自动目录授权"',
    1,
)
manifest.write_text(m, encoding="utf-8")

print("Applied v0.5 global Android/data interception + Xiaomi/HyperOS accessibility guidance")
