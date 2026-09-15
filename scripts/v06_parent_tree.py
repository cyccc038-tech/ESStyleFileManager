#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: v06_parent_tree.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"

# v0.6
build = app / "build.gradle"
text = build.read_text(encoding="utf-8")
for old, new in [
    ("versionCode 10005", "versionCode 10006"),
    ("versionName '1.7.4-esstyle.5'", "versionName '1.7.4-esstyle.6'"),
]:
    if old not in text:
        raise RuntimeError(f"Expected version marker not found: {old}")
    text = text.replace(old, new, 1)
build.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# 1) Make any user-added SAF tree behave transparently inside the normal file list.
#    This is the important finding from the Xiaomi test: when the same directory is added through
#    "Add storage -> Folder", Material Files uses its DocumentProvider backend and can see/write
#    entries that the raw /storage/emulated/0 java.nio backend cannot. We therefore route matching
#    local paths through the persisted SAF tree automatically.
# ---------------------------------------------------------------------------
fragment = app / "src/main/java/me/zhanghai/android/files/filelist/FileListFragment.kt"
f = fragment.read_text(encoding="utf-8")

if "import android.provider.DocumentsContract\n" not in f:
    f = f.replace("import android.os.Looper\n", "import android.os.Looper\nimport android.provider.DocumentsContract\n", 1)
if "import me.zhanghai.android.files.storage.DocumentTree\n" not in f:
    f = f.replace("import me.zhanghai.android.files.settings.Settings\n", "import me.zhanghai.android.files.settings.Settings\nimport me.zhanghai.android.files.storage.DocumentTree\n", 1)

old_block = '''    private fun esAndroidSpecialTarget(path: Path): String? {
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

new_block = '''    private fun esAndroidSpecialTarget(path: Path): String? {
        val value = path.toString().replace('\\\\', '/').trimEnd('/')
        return when {
            value.endsWith("/Android/data", ignoreCase = true) -> "data"
            value.endsWith("/Android/obb", ignoreCase = true) -> "obb"
            else -> null
        }
    }

    private fun esPrimaryTreePrefix(tree: DocumentTree): String? {
        val documentId = runCatching { DocumentsContract.getTreeDocumentId(tree.uri.value) }
            .getOrNull() ?: return null
        if (!documentId.startsWith("primary:")) return null
        return documentId.removePrefix("primary:").trim('/')
    }

    /**
     * Map /storage/emulated/0/... to the most-specific persisted SAF tree that covers the path.
     * Example: if the user granted the Android folder once, then normal navigation to
     * /storage/emulated/0/Android/data is transparently rerouted to the DocumentProvider path.
     */
    private fun esMapToDocumentTree(path: Path): Path? {
        val raw = path.toString().replace('\\\\', '/').trimEnd('/')
        @Suppress("DEPRECATION")
        val primaryRoot = Environment.getExternalStorageDirectory().absolutePath
            .replace('\\\\', '/').trimEnd('/')
        val relative = when {
            raw == primaryRoot -> ""
            raw.startsWith("$primaryRoot/") -> raw.removePrefix("$primaryRoot/").trim('/')
            else -> return null
        }

        val candidates = Settings.STORAGES.valueCompat.filterIsInstance<DocumentTree>()
            .mapNotNull { tree ->
                val prefix = esPrimaryTreePrefix(tree) ?: return@mapNotNull null
                val covered = prefix.isEmpty() || relative == prefix || relative.startsWith("$prefix/")
                if (covered) tree to prefix else null
            }
        val (tree, prefix) = candidates.maxByOrNull { it.second.length } ?: return null

        var mapped = tree.path
        val suffix = if (prefix.isEmpty()) relative else relative.removePrefix(prefix).trimStart('/')
        if (suffix.isNotEmpty()) {
            for (segment in suffix.split('/')) {
                if (segment.isNotEmpty()) mapped = mapped.resolve(segment)
            }
        }
        return mapped
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
        // Prefer a persisted SAF tree over the raw Linux provider. This makes a one-time
        // "Add storage -> Folder" permission act like ES's transparent hidden-file access.
        val mapped = esMapToDocumentTree(path)
        if (mapped != null && mapped.toString() != path.toString()) {
            collapseSearchView()
            val state = layoutManager.onSaveInstanceState()
            viewModel.navigateTo(state!!, mapped)
            return
        }

        // If Android/data or obb is not covered by a saved parent-tree grant yet, request the
        // Android parent folder once. After that all future navigation is transparent.
        if (openEsAndroidSpecial(path)) return
        collapseSearchView()
        val state = layoutManager.onSaveInstanceState()
        viewModel.navigateTo(state!!, path)
    }'''

if old_block not in f:
    raise RuntimeError("Could not locate v0.5 Android/data navigation block")
f = f.replace(old_block, new_block, 1)

# Map the initial/default directory as well, so reopening the app reuses the SAF backend directly.
startup_old = '''            if (path == null) {
                path = Settings.FILE_LIST_DEFAULT_DIRECTORY.valueCompat
            }
            viewModel.resetTo(path)'''
startup_new = '''            if (path == null) {
                path = Settings.FILE_LIST_DEFAULT_DIRECTORY.valueCompat
            }
            path = esMapToDocumentTree(path) ?: path
            viewModel.resetTo(path)'''
if startup_old not in f:
    raise RuntimeError("Could not locate initial-path block")
f = f.replace(startup_old, startup_new, 1)

# On upgrade, recover a stale raw-path activity before it can show AccessDeniedException.
current_old = '''    private fun onCurrentPathChanged(path: Path) {
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
current_new = '''    private fun onCurrentPathChanged(path: Path) {
        // If a saved SAF tree covers this raw local path, transparently switch providers first.
        val mapped = esMapToDocumentTree(path)
        if (mapped != null && mapped.toString() != path.toString()) {
            viewModel.resetTo(mapped)
            return
        }

        // Recover a restored raw Android/data path only when no parent-tree SAF permission exists.
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
    raise RuntimeError("Could not locate v0.5 onCurrentPathChanged block")
f = f.replace(current_old, current_new, 1)
fragment.write_text(f, encoding="utf-8")

# ---------------------------------------------------------------------------
# 2) One-time grant of the *Android parent folder*, not Android/data itself.
#    Xiaomi's DocumentsUI correctly blocks selecting Android/data, but the Android parent folder is
#    selectable. The resulting tree is persisted and normal file navigation is then remapped to it.
# ---------------------------------------------------------------------------
data_activity = app / "src/main/java/me/zhanghai/android/files/esstyle/EsAndroidDataActivity.kt"
data_activity.write_text(r'''package me.zhanghai.android.files.esstyle

import android.net.Uri
import android.os.Bundle
import android.provider.DocumentsContract
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import me.zhanghai.android.files.app.AppActivity
import me.zhanghai.android.files.file.asDocumentTreeUriOrNull
import me.zhanghai.android.files.file.takePersistablePermission
import me.zhanghai.android.files.filelist.FileListActivity
import me.zhanghai.android.files.settings.Settings
import me.zhanghai.android.files.storage.DocumentTree
import me.zhanghai.android.files.storage.Storages
import me.zhanghai.android.files.util.launchSafe
import me.zhanghai.android.files.util.valueCompat

/**
 * Bridge for Android/data and Android/obb on Android 11+.
 *
 * We never ask DocumentsUI to grant Android/data itself because the system intentionally disables
 * that button. Instead we ask once for the parent Android directory, persist that tree permission,
 * and resolve data/obb below the granted tree. Subsequent access is direct and requires no picker.
 */
class EsAndroidDataActivity : AppActivity() {

    private var target = "data"

    private val openAndroidTreeLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocumentTree(), this::onAndroidTreeResult
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        target = intent.getStringExtra(EXTRA_TARGET).takeUnless { it.isNullOrBlank() } ?: "data"
        Settings.FILE_LIST_SHOW_HIDDEN_FILES.putValue(true)

        findCoveringTree()?.let {
            openTarget(it)
            return
        }

        if (savedInstanceState == null) {
            Toast.makeText(
                this,
                "首次只需授权一次 Android 文件夹。以后 Android/data 会直接打开，不再重复授权。",
                Toast.LENGTH_LONG
            ).show()
            openAndroidTreeLauncher.launchSafe(buildAndroidInitialUri(), this)
        }
    }

    private fun onAndroidTreeResult(result: Uri?) {
        val treeUri = result?.asDocumentTreeUriOrNull()
        if (treeUri == null) {
            Toast.makeText(this, "未授权 Android 文件夹", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        val documentId = runCatching { DocumentsContract.getTreeDocumentId(treeUri.value) }
            .getOrNull().orEmpty()
        val prefix = documentId.removePrefix("primary:").trim('/')
        if (!documentId.startsWith("primary:") ||
            !(prefix.isEmpty() || "Android/$target" == prefix || "Android/$target".startsWith("$prefix/"))) {
            Toast.makeText(
                this,
                "请选择“Android”文件夹（不要进入 data 再选择）",
                Toast.LENGTH_LONG
            ).show()
            finish()
            return
        }

        treeUri.takePersistablePermission()
        val tree = DocumentTree(null, if (prefix == "Android") "Android（完整访问）" else null, treeUri)
        Storages.addOrReplace(tree)
        openTarget(tree)
    }

    private fun findCoveringTree(): DocumentTree? {
        val relative = "Android/$target"
        return Settings.STORAGES.valueCompat.filterIsInstance<DocumentTree>()
            .mapNotNull { tree ->
                val id = runCatching { DocumentsContract.getTreeDocumentId(tree.uri.value) }
                    .getOrNull() ?: return@mapNotNull null
                if (!id.startsWith("primary:")) return@mapNotNull null
                val prefix = id.removePrefix("primary:").trim('/')
                val covered = prefix.isEmpty() || relative == prefix || relative.startsWith("$prefix/")
                if (covered) tree to prefix else null
            }
            .maxByOrNull { it.second.length }
            ?.first
    }

    private fun openTarget(tree: DocumentTree) {
        val id = runCatching { DocumentsContract.getTreeDocumentId(tree.uri.value) }
            .getOrNull() ?: run {
            finish()
            return
        }
        val prefix = id.removePrefix("primary:").trim('/')
        val relative = "Android/$target"
        if (!(prefix.isEmpty() || relative == prefix || relative.startsWith("$prefix/"))) {
            finish()
            return
        }

        var path = tree.path
        val suffix = if (prefix.isEmpty()) relative else relative.removePrefix(prefix).trimStart('/')
        if (suffix.isNotEmpty()) {
            suffix.split('/').filter { it.isNotEmpty() }.forEach { path = path.resolve(it) }
        }
        startActivity(FileListActivity.createViewIntent(path))
        finish()
    }

    private fun buildAndroidInitialUri(): Uri =
        DocumentsContract.buildDocumentUri(AUTHORITY, "primary:Android")

    companion object {
        const val EXTRA_TARGET = "target"
        private const val AUTHORITY = "com.android.externalstorage.documents"
    }
}
''', encoding="utf-8")

# ---------------------------------------------------------------------------
# 3) When the user manually adds a folder through "Add storage", make that permission immediately
#    useful: keep hidden files enabled and name an Android parent grant clearly.
# ---------------------------------------------------------------------------
add_fragment = app / "src/main/java/me/zhanghai/android/files/storage/AddDocumentTreeFragment.kt"
a = add_fragment.read_text(encoding="utf-8")
if "import android.provider.DocumentsContract\n" not in a:
    a = a.replace("import android.os.Bundle\n", "import android.os.Bundle\nimport android.provider.DocumentsContract\n", 1)
if "import me.zhanghai.android.files.settings.Settings\n" not in a:
    a = a.replace("import me.zhanghai.android.files.file.takePersistablePermission\n", "import me.zhanghai.android.files.file.takePersistablePermission\nimport me.zhanghai.android.files.settings.Settings\n", 1)
old_add = '''    private fun addDocumentTree(treeUri: DocumentTreeUri) {
        treeUri.takePersistablePermission()
        val documentTree = DocumentTree(null, null, treeUri)
        Storages.addOrReplace(documentTree)
    }'''
new_add = '''    private fun addDocumentTree(treeUri: DocumentTreeUri) {
        treeUri.takePersistablePermission()
        val documentId = runCatching { DocumentsContract.getTreeDocumentId(treeUri.value) }
            .getOrNull().orEmpty()
        val customName = when (documentId) {
            "primary:Android" -> "Android（完整访问）"
            "primary:" -> "内部存储（完整访问）"
            else -> null
        }
        val documentTree = DocumentTree(null, customName, treeUri)
        Storages.addOrReplace(documentTree)
        Settings.FILE_LIST_SHOW_HIDDEN_FILES.putValue(true)
    }'''
if old_add not in a:
    raise RuntimeError("Could not locate AddDocumentTreeFragment.addDocumentTree()")
a = a.replace(old_add, new_add, 1)
add_fragment.write_text(a, encoding="utf-8")

# ---------------------------------------------------------------------------
# 4) Remove the experimental accessibility auto-click service from v0.4/v0.5. It is no longer
#    needed with the parent-tree approach and removing it is better for privacy and Xiaomi UX.
# ---------------------------------------------------------------------------
manifest = app / "src/main/AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")
m = re.sub(
    r'\n\s*<service\s+android:name="me\.zhanghai\.android\.files\.esstyle\.EsAutoAuthService".*?</service>\s*',
    '\n', m, flags=re.S
)
m = re.sub(
    r'\n\s*<activity\s+android:name="me\.zhanghai\.android\.files\.esstyle\.EsBatchGrantActivity".*?/>\s*',
    '\n', m, flags=re.S
)
manifest.write_text(m, encoding="utf-8")

# Update the prototype home copy so it no longer mentions per-app accessibility grants.
home = app / "src/main/java/me/zhanghai/android/files/esstyle/EsHomeActivity.kt"
h = home.read_text(encoding="utf-8")
h = h.replace(
    'ES 无 Root 兼容模式：按应用目录自动授权并合并显示',
    '无 Root：首次授权 Android 父目录一次，之后直接读取和修改',
)
home.write_text(h, encoding="utf-8")

print("Applied v0.6 parent-tree SAF: one Android-folder grant, transparent remapping, hidden files on")
