#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: es_android_data_auth.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"
if not (app / "build.gradle").exists():
    raise SystemExit(f"Not a Material Files checkout: {root}")

# Match the modern ES File Explorer branch more closely: it targets Android 11/API 30 and declares
# MANAGE_EXTERNAL_STORAGE. Android/data itself is still protected, so access there is handled by the
# per-package SAF authorization flow implemented below.
build = app / "build.gradle"
text = build.read_text(encoding="utf-8")
text = text.replace("targetSdk 29", "targetSdk 30", 1)
text = text.replace("versionCode 10003", "versionCode 10004", 1)
text = text.replace("versionName '1.7.4-esstyle.3'", "versionName '1.7.4-esstyle.4'", 1)
build.write_text(text, encoding="utf-8")

manifest = app / "src/main/AndroidManifest.xml"
manifest_text = manifest.read_text(encoding="utf-8")

# Needed to enumerate installed packages when Android/data itself cannot be listed. This mirrors the
# fallback used by ES: enumerate packages and request a tree grant for each existing app directory.
if 'android.permission.QUERY_ALL_PACKAGES' not in manifest_text:
    manifest_text = manifest_text.replace(
        '<uses-permission android:name="android.permission.INTERNET" />',
        '<uses-permission android:name="android.permission.INTERNET" />\n'
        '    <uses-permission android:name="android.permission.QUERY_ALL_PACKAGES" />',
        1,
    )

service_block = '''
        <service
            android:name="me.zhanghai.android.files.esstyle.EsAutoAuthService"
            android:exported="true"
            android:label="@string/app_name"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/es_auto_auth_service" />
        </service>
'''
if 'me.zhanghai.android.files.esstyle.EsAutoAuthService' not in manifest_text:
    pos = manifest_text.rfind('</application>')
    if pos < 0:
        raise RuntimeError('Could not locate </application>')
    manifest_text = manifest_text[:pos] + service_block + manifest_text[pos:]

activity_block = '''
        <activity
            android:name="me.zhanghai.android.files.esstyle.EsAndroidDataActivity"
            android:exported="false"
            android:label="Android/data" />
        <activity
            android:name="me.zhanghai.android.files.esstyle.EsBatchGrantActivity"
            android:exported="false"
            android:label="Android/data 授权" />
'''
if 'me.zhanghai.android.files.esstyle.EsAndroidDataActivity' not in manifest_text:
    anchor = '        <activity\n            android:name="me.zhanghai.android.files.esstyle.EsDocumentTreeGrantActivity"'
    if anchor not in manifest_text:
        raise RuntimeError('Could not locate EsDocumentTreeGrantActivity manifest entry')
    manifest_text = manifest_text.replace(anchor, activity_block + anchor, 1)

manifest.write_text(manifest_text, encoding="utf-8")

xml_dir = app / "src/main/res/xml"
xml_dir.mkdir(parents=True, exist_ok=True)
(xml_dir / "es_auto_auth_service.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged|typeViewClicked"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="80"
    android:canRetrieveWindowContent="true"
    android:accessibilityFlags="flagReportViewIds" />
''', encoding="utf-8")

src_dir = app / "src/main/java/me/zhanghai/android/files/esstyle"
src_dir.mkdir(parents=True, exist_ok=True)

(src_dir / "EsAutoAuthService.kt").write_text(r'''package me.zhanghai.android.files.esstyle

import android.accessibilityservice.AccessibilityService
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * ES-style one-time SAF helper.
 *
 * The service only acts while an explicit Android/data authorization batch is active and expires
 * automatically. It only reacts to Android DocumentsUI windows and only clicks the folder-grant or
 * confirmation buttons. It does not automate any other application.
 */
class EsAutoAuthService : AccessibilityService() {

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (!isBatchActive()) return
        val packageName = event?.packageName?.toString() ?: return
        if (packageName != "com.google.android.documentsui" &&
            packageName != "com.android.documentsui") return

        val root = rootInActiveWindow ?: return
        if (clickFirstEnabled(root, GRANT_TEXTS)) return
        clickFirstEnabled(root, CONFIRM_TEXTS)
    }

    override fun onInterrupt() = Unit

    private fun isBatchActive(): Boolean {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        if (!prefs.getBoolean(KEY_ACTIVE, false)) return false
        val expiresAt = prefs.getLong(KEY_EXPIRES_AT, 0L)
        if (SystemClock.elapsedRealtime() > expiresAt) {
            prefs.edit().putBoolean(KEY_ACTIVE, false).apply()
            return false
        }
        return true
    }

    private fun clickFirstEnabled(root: AccessibilityNodeInfo, texts: Array<String>): Boolean {
        for (text in texts) {
            val nodes = root.findAccessibilityNodeInfosByText(text) ?: continue
            for (node in nodes) {
                var current: AccessibilityNodeInfo? = node
                repeat(4) {
                    val candidate = current ?: return@repeat
                    if (candidate.isEnabled && candidate.isClickable) {
                        if (candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
                    }
                    current = candidate.parent
                }
            }
        }
        return false
    }

    companion object {
        const val PREFS = "es_android_data_auth"
        const val KEY_ACTIVE = "active"
        const val KEY_EXPIRES_AT = "expires_at"

        // ES itself uses localized grant/confirm text arrays. Cover the common AOSP/Xiaomi strings.
        private val GRANT_TEXTS = arrayOf(
            "使用此文件夹", "Use this folder", "选择此文件夹", "Select this folder", "选择", "Select"
        )
        private val CONFIRM_TEXTS = arrayOf(
            "允许", "Allow", "确定", "OK", "继续", "Continue"
        )
    }
}
''', encoding="utf-8")

(src_dir / "EsBatchGrantActivity.kt").write_text(r'''package me.zhanghai.android.files.esstyle

import android.content.ComponentName
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.os.SystemClock
import android.provider.DocumentsContract
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import me.zhanghai.android.files.app.AppActivity
import me.zhanghai.android.files.file.asDocumentTreeUriOrNull
import me.zhanghai.android.files.file.takePersistablePermission
import java.io.File

/**
 * Requests SAF access to Android/data or Android/obb one application directory at a time.
 *
 * This is intentionally different from trying to grant Android/data itself: current DocumentsUI
 * blocks the root directory. ES File Explorer's modern implementation falls back to enumerating app
 * package directories and authorizing them individually; this activity implements that behavior.
 */
class EsBatchGrantActivity : AppActivity() {

    private var target = "data"
    private var packages = arrayListOf<String>()
    private var index = 0

    private val launcher = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        uri?.asDocumentTreeUriOrNull()?.let { treeUri ->
            runCatching { treeUri.takePersistablePermission() }
        }
        index += 1
        launchNext()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        target = intent.getStringExtra(EXTRA_TARGET).takeUnless { it.isNullOrBlank() } ?: "data"

        if (!isAccessibilityServiceEnabled()) {
            getSharedPreferences(EsAutoAuthService.PREFS, MODE_PRIVATE).edit()
                .putBoolean(EsAutoAuthService.KEY_ACTIVE, false).apply()
            Toast.makeText(
                this,
                "ES 的无 Root 方案需要本应用的“自动目录授权”无障碍服务。请启用后返回，再进入 Android/$target。",
                Toast.LENGTH_LONG
            ).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            finish()
            return
        }

        if (savedInstanceState == null) {
            packages = ArrayList(buildPackageTargets(target))
            index = 0
        } else {
            packages = savedInstanceState.getStringArrayList(STATE_PACKAGES) ?: arrayListOf()
            index = savedInstanceState.getInt(STATE_INDEX, 0)
        }

        if (packages.isEmpty()) {
            Toast.makeText(this, "没有发现需要新增授权的应用目录", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        setBatchActive(true)
        launchNext()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putStringArrayList(STATE_PACKAGES, packages)
        outState.putInt(STATE_INDEX, index)
        super.onSaveInstanceState(outState)
    }

    private fun launchNext() {
        if (index >= packages.size) {
            setBatchActive(false)
            Toast.makeText(this, "Android/$target 目录授权完成", Toast.LENGTH_LONG).show()
            finish()
            return
        }
        val pkg = packages[index]
        title = "授权 ${index + 1}/${packages.size}: $pkg"
        val initialUri = buildInitialDocumentUri(target, pkg)
        runCatching { launcher.launch(initialUri) }
            .onFailure {
                index += 1
                launchNext()
            }
    }

    private fun buildPackageTargets(target: String): List<String> {
        val base = File(Environment.getExternalStorageDirectory(), "Android/$target")
        val direct = runCatching {
            base.listFiles()?.filter { it.isDirectory }?.map { it.name }.orEmpty()
        }.getOrDefault(emptyList())

        val candidates = if (direct.isNotEmpty()) {
            direct
        } else {
            @Suppress("DEPRECATION")
            packageManager.getInstalledPackages(0).map { it.packageName }
                .filter { pkg ->
                    // File.exists() often remains usable even when listing Android/data is blocked.
                    // If the OEM blocks even this metadata check, fall back to all installed apps.
                    runCatching { File(base, pkg).exists() }.getOrDefault(false)
                }.let { existing ->
                    if (existing.isNotEmpty()) existing
                    else @Suppress("DEPRECATION") packageManager.getInstalledPackages(0).map { it.packageName }
                }
        }

        val alreadyGranted = persistedPackages(target)
        return candidates.distinct().filterNot { it in alreadyGranted }.sorted()
    }

    private fun persistedPackages(target: String): Set<String> {
        val prefix = "primary:Android/$target/"
        return contentResolver.persistedUriPermissions.mapNotNull { permission ->
            val id = runCatching { DocumentsContract.getTreeDocumentId(permission.uri) }.getOrNull()
                ?: return@mapNotNull null
            if (!id.startsWith(prefix)) return@mapNotNull null
            id.removePrefix(prefix).substringBefore('/').takeIf { it.isNotBlank() }
        }.toSet()
    }

    private fun buildInitialDocumentUri(target: String, pkg: String): Uri {
        val docId = "primary:Android/$target/$pkg"
        val tree = DocumentsContract.buildTreeDocumentUri(AUTHORITY, docId)
        return DocumentsContract.buildDocumentUriUsingTree(tree, docId)
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val expected = ComponentName(this, EsAutoAuthService::class.java)
        val enabled = Settings.Secure.getString(
            contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabled.split(':').any { value ->
            ComponentName.unflattenFromString(value)?.let {
                it.packageName == expected.packageName && it.className == expected.className
            } == true
        }
    }

    private fun setBatchActive(active: Boolean) {
        getSharedPreferences(EsAutoAuthService.PREFS, MODE_PRIVATE).edit()
            .putBoolean(EsAutoAuthService.KEY_ACTIVE, active)
            .putLong(
                EsAutoAuthService.KEY_EXPIRES_AT,
                if (active) SystemClock.elapsedRealtime() + 10 * 60 * 1000L else 0L
            )
            .apply()
    }

    companion object {
        const val EXTRA_TARGET = "target"
        private const val STATE_PACKAGES = "packages"
        private const val STATE_INDEX = "index"
        private const val AUTHORITY = "com.android.externalstorage.documents"
    }
}
''', encoding="utf-8")

(src_dir / "EsAndroidDataActivity.kt").write_text(r'''package me.zhanghai.android.files.esstyle

import android.content.ComponentName
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.provider.DocumentsContract
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import me.zhanghai.android.files.app.AppActivity
import me.zhanghai.android.files.file.asDocumentTreeUriOrNull
import me.zhanghai.android.files.filelist.FileListActivity
import me.zhanghai.android.files.storage.DocumentTree

/** Synthetic Android/data (or obb) browser backed by persisted per-package SAF grants. */
class EsAndroidDataActivity : AppActivity() {

    private var target = "data"
    private lateinit var content: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        target = intent.getStringExtra(EXTRA_TARGET).takeUnless { it.isNullOrBlank() } ?: "data"
        title = "Android/$target"
        setContentView(buildView())
    }

    override fun onResume() {
        super.onResume()
        if (::content.isInitialized) refreshGrantedFolders()
    }

    private fun buildView(): View {
        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(24))
        }
        scroll.addView(root)

        root.addView(TextView(this).apply {
            text = "Android/$target 在新 Android 上不能作为一个普通目录直接读取。此版本按 ES 的现代做法，对每个应用子目录分别取得系统 SAF 授权，然后在这里合并显示。无需 Root 或 Shizuku。"
            textSize = 14f
            setTextColor(Color.DKGRAY)
            setPadding(0, 0, 0, dp(12))
        })

        root.addView(Button(this).apply {
            text = "自动授权全部应用目录"
            setOnClickListener { startBatchGrant() }
        })

        root.addView(Button(this).apply {
            text = "打开无障碍设置"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })

        root.addView(TextView(this).apply {
            text = "已授权目录"
            textSize = 17f
            setTextColor(Color.BLACK)
            setPadding(0, dp(18), 0, dp(8))
        })

        content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(content)
        return scroll
    }

    private fun refreshGrantedFolders() {
        content.removeAllViews()
        val prefix = "primary:Android/$target/"
        val grants = contentResolver.persistedUriPermissions.mapNotNull { permission ->
            val id = runCatching { DocumentsContract.getTreeDocumentId(permission.uri) }.getOrNull()
                ?: return@mapNotNull null
            if (!id.startsWith(prefix)) return@mapNotNull null
            val pkg = id.removePrefix(prefix).substringBefore('/').takeIf { it.isNotBlank() }
                ?: return@mapNotNull null
            pkg to permission.uri
        }.distinctBy { it.first }.sortedBy { it.first }

        if (grants.isEmpty()) {
            content.addView(TextView(this).apply {
                text = "还没有 Android/$target 子目录授权。点击上方“自动授权全部应用目录”。"
                setTextColor(Color.GRAY)
                textSize = 14f
                setPadding(dp(8), dp(16), dp(8), dp(16))
            })
            return
        }

        for ((pkg, uri) in grants) {
            content.addView(TextView(this).apply {
                text = pkg
                textSize = 15f
                setTextColor(Color.rgb(35, 39, 47))
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(14), dp(15), dp(14), dp(15))
                setBackgroundColor(Color.rgb(246, 247, 249))
                setOnClickListener {
                    val treeUri = uri.asDocumentTreeUriOrNull()
                    if (treeUri == null) {
                        Toast.makeText(this@EsAndroidDataActivity, "目录授权已失效", Toast.LENGTH_SHORT).show()
                        return@setOnClickListener
                    }
                    val tree = DocumentTree(null, pkg, treeUri)
                    startActivity(FileListActivity.createViewIntent(tree.path))
                }
            }, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(6) })
        }
    }

    private fun startBatchGrant() {
        if (!isAccessibilityServiceEnabled()) {
            Toast.makeText(
                this,
                "先启用“ESStyle 文件管理器”的自动目录授权无障碍服务；这是 ES 实际使用的无 Root 自动授权思路。",
                Toast.LENGTH_LONG
            ).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }
        startActivity(
            Intent(this, EsBatchGrantActivity::class.java)
                .putExtra(EsBatchGrantActivity.EXTRA_TARGET, target)
        )
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val expected = ComponentName(this, EsAutoAuthService::class.java)
        val enabled = Settings.Secure.getString(
            contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabled.split(':').any { value ->
            ComponentName.unflattenFromString(value)?.let {
                it.packageName == expected.packageName && it.className == expected.className
            } == true
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()

    companion object {
        const val EXTRA_TARGET = "target"
    }
}
''', encoding="utf-8")

# Replace the prototype direct/SAF rows in the home screen with the synthetic ES-style browsers.
home = src_dir / "EsHomeActivity.kt"
home_text = home.read_text(encoding="utf-8")
start = home_text.index('        root.addView(actionRow("Android / data"')
end_marker = '        root.addView(actionRow("完整文件管理"'
end = home_text.index(end_marker, start)
replacement = '''        root.addView(actionRow("Android / data", "ES 无 Root 兼容模式：按应用目录自动授权并合并显示") {
            startActivity(Intent(this, EsAndroidDataActivity::class.java).putExtra(EsAndroidDataActivity.EXTRA_TARGET, "data"))
        })
        root.addView(actionRow("Android / obb", "ES 无 Root 兼容模式：按应用目录自动授权并合并显示") {
            startActivity(Intent(this, EsAndroidDataActivity::class.java).putExtra(EsAndroidDataActivity.EXTRA_TARGET, "obb"))
        })
'''
home_text = home_text[:start] + replacement + home_text[end:]
home.write_text(home_text, encoding="utf-8")

print("Applied ES-style per-package Android/data SAF authorization + temporary accessibility auto-grant")
