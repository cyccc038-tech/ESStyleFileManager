#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: legacy_compat.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Keep Android 11 SAF compatibility behavior available for Android/data and Android/obb.
build = app / "build.gradle"
text = build.read_text(encoding="utf-8")
for old, new in [
    ("targetSdk 34", "targetSdk 29"),
    ("versionCode 10001", "versionCode 10003"),
    ("versionName '1.7.4-esstyle.1'", "versionName '1.7.4-esstyle.3'"),
]:
    if old not in text:
        raise RuntimeError(f"Expected build.gradle text not found: {old}")
    text = text.replace(old, new, 1)
build.write_text(text, encoding="utf-8")

# ES-style defaults for this privacy build: show dot-files and never silently jump to root.
prefs = app / "src/main/res/values/donottranslate_prefs.xml"
prefs_text = prefs.read_text(encoding="utf-8")
if '<bool name="pref_default_value_file_list_show_hidden_files">true</bool>' not in prefs_text:
    raise RuntimeError("Hidden-file default was not enabled by customize.py")
prefs_text = prefs_text.replace(
    '<string name="pref_default_value_root_strategy">1</string>',
    '<string name="pref_default_value_root_strategy">0</string>',
    1,
)
prefs.write_text(prefs_text, encoding="utf-8")

# Material Files intentionally treats other apps' Android/data and Android/obb as root-only on
# Android 11+, regardless of targetSdk. That is why v0.2 showed "Root isn't available". For this
# compatibility build we MUST try the normal local provider first. If the OS blocks it, the ES home
# automatically falls back to SAF instead of asking for root.
linux_path = app / "src/main/java/me/zhanghai/android/files/provider/linux/LinuxPath.kt"
linux_text = linux_path.read_text(encoding="utf-8")
old_restricted = '''        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val parentDirectory = parentFile
            val androidDataDirectory = storageVolumeDirectory.resolve(FILE_ANDROID_DATA)
            val isInAndroidDataDirectory = if (isAttributeAccess && parentDirectory != null) {
                parentDirectory.startsWith(androidDataDirectory)
            } else {
                startsWith(androidDataDirectory)
            }
            val appPackageName = application.packageName
            if (isInAndroidDataDirectory) {
                val appDataDirectory = androidDataDirectory.resolve(appPackageName)
                return startsWith(appDataDirectory)
            }
            val androidObbDirectory = storageVolumeDirectory.resolve(FILE_ANDROID_OBB)
            val isInAndroidObbDirectory = if (isAttributeAccess && parentDirectory != null) {
                parentDirectory.startsWith(androidObbDirectory)
            } else {
                startsWith(androidObbDirectory)
            }
            if (isInAndroidObbDirectory) {
                val appObbDirectory = androidObbDirectory.resolve(appPackageName)
                return startsWith(appObbDirectory)
            }
        }
        return true'''
new_restricted = '''        // ESStyle compatibility mode: do not reroute Android/data or Android/obb to libsu.
        // We intentionally attempt normal local access first. On ROMs that retain legacy access
        // this works directly; on stricter Android builds EsHomeActivity falls back to SAF.
        return true'''
if old_restricted not in linux_text:
    raise RuntimeError("Could not locate Android/data root-routing block in LinuxPath.kt")
linux_path.write_text(linux_text.replace(old_restricted, new_restricted, 1), encoding="utf-8")

home = app / "src/main/java/me/zhanghai/android/files/esstyle/EsHomeActivity.kt"
text = home.read_text(encoding="utf-8")

# Required imports for persistent SAF reuse and enforced ES-style defaults.
text = text.replace(
    'import android.os.StatFs\n',
    'import android.os.StatFs\nimport android.provider.DocumentsContract\n',
    1,
)
text = text.replace(
    'import java8.nio.file.Paths\n',
    'import java8.nio.file.Paths\nimport me.zhanghai.android.files.file.asDocumentTreeUriOrNull\n',
    1,
)
text = text.replace(
    'import me.zhanghai.android.files.settings.SettingsActivity\n',
    'import me.zhanghai.android.files.settings.Settings\nimport me.zhanghai.android.files.settings.SettingsActivity\nimport me.zhanghai.android.files.provider.root.RootStrategy\n',
    1,
)
text = text.replace(
    'import me.zhanghai.android.files.storage.AddStorageDialogActivity\n',
    'import me.zhanghai.android.files.storage.AddStorageDialogActivity\nimport me.zhanghai.android.files.storage.DocumentTree\nimport java.io.File\n',
    1,
)

old_on_create = '''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "ESStyle 文件管理器"
        setContentView(buildHome())
    }'''
new_on_create = '''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Keep the ES behavior requested for this build even when upgrading over an older test APK
        // whose SharedPreferences may have persisted different defaults.
        Settings.FILE_LIST_SHOW_HIDDEN_FILES.putValue(true)
        Settings.ROOT_STRATEGY.putValue(RootStrategy.NEVER)
        title = "ESStyle 文件管理器"
        setContentView(buildHome())
    }'''
if old_on_create not in text:
    raise RuntimeError("Could not locate EsHomeActivity.onCreate()")
text = text.replace(old_on_create, new_on_create, 1)

old_rows = '''        root.addView(actionRow("Android / data", "无 Root：通过系统文档授权访问；授权后会加入侧栏") {
            grantAndroidTree("data")
        })
        root.addView(actionRow("Android / obb", "无 Root：通过系统文档授权访问；授权后会加入侧栏") {
            grantAndroidTree("obb")
        })'''
new_rows = '''        root.addView(actionRow("Android / data", "无 Root：已授权则直接打开；否则先尝试本地访问，失败自动进入系统目录授权") {
            openAndroidSpecial("data")
        })
        root.addView(actionRow("Android / obb", "无 Root：已授权则直接打开；否则先尝试本地访问，失败自动进入系统目录授权") {
            openAndroidSpecial("obb")
        })'''
if old_rows not in text:
    raise RuntimeError("Could not locate Android/data home rows")
text = text.replace(old_rows, new_rows, 1)

anchor = '''    private fun grantAndroidTree(target: String) {
        startActivity(Intent(this, EsDocumentTreeGrantActivity::class.java).putExtra("target", target))
    }
'''
insert = '''    private fun openAndroidSpecial(target: String) {
        if (openPersistedAndroidTree(target)) {
            return
        }

        val base = Environment.getExternalStorageDirectory()
        val directory = File(File(base, "Android"), target)
        val locallyReadable = runCatching { directory.listFiles() != null }.getOrDefault(false)
        if (locallyReadable) {
            runCatching {
                startActivity(FileListActivity.createViewIntent(Paths.get(directory.absolutePath)))
            }.onFailure { grantAndroidTree(target) }
        } else {
            Toast.makeText(
                this,
                "系统限制了直接访问，正在切换到无 Root 目录授权",
                Toast.LENGTH_LONG
            ).show()
            grantAndroidTree(target)
        }
    }

    private fun openPersistedAndroidTree(target: String): Boolean {
        val documentId = "primary:Android/$target"
        val permission = contentResolver.persistedUriPermissions.firstOrNull {
            runCatching { DocumentsContract.getTreeDocumentId(it.uri) == documentId }
                .getOrDefault(false)
        } ?: return false
        val treeUri = permission.uri.asDocumentTreeUriOrNull() ?: return false
        val documentTree = DocumentTree(null, "Android/$target", treeUri)
        startActivity(FileListActivity.createViewIntent(documentTree.path))
        return true
    }

'''
if anchor not in text:
    raise RuntimeError("Could not locate grantAndroidTree()")
text = text.replace(anchor, insert + anchor, 1)
home.write_text(text, encoding="utf-8")

# After a one-time SAF grant, open the granted tree immediately instead of returning to an error page.
grant = app / "src/main/java/me/zhanghai/android/files/esstyle/EsDocumentTreeGrantActivity.kt"
grant_text = grant.read_text(encoding="utf-8")
grant_text = grant_text.replace(
    'import me.zhanghai.android.files.file.takePersistablePermission\n',
    'import me.zhanghai.android.files.file.takePersistablePermission\nimport me.zhanghai.android.files.filelist.FileListActivity\n',
    1,
)
old_add = '''                treeUri.takePersistablePermission()
                Storages.addOrReplace(DocumentTree(null, null, treeUri))'''
new_add = '''                treeUri.takePersistablePermission()
                val documentTree = DocumentTree(null, "Android/${intent.getStringExtra("target") ?: "data"}", treeUri)
                Storages.addOrReplace(documentTree)
                startActivity(FileListActivity.createViewIntent(documentTree.path))'''
if old_add not in grant_text:
    raise RuntimeError("Could not locate SAF persistence block")
grant.write_text(grant_text.replace(old_add, new_add, 1), encoding="utf-8")

print("Applied v0.3 Android/data local-first + SAF fallback, no-root routing and hidden-file defaults")
