#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: customize.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"
if not (app / "build.gradle").exists():
    raise SystemExit(f"Not a Material Files checkout: {root}")


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# Keep upstream code namespace intact, but give the customized app its own install identity.
build_gradle = app / "build.gradle"
replace(build_gradle, "applicationId 'me.zhanghai.android.files'", "applicationId 'com.cyccc038.esstylefiles'")
replace(build_gradle, "versionCode 39", "versionCode 10001")
replace(build_gradle, "versionName '1.7.4'", "versionName '1.7.4-esstyle.1'")

# ES-like behavior: hidden files are visible by default, but the original toggle remains available.
prefs = app / "src/main/res/values/donottranslate_prefs.xml"
replace(
    prefs,
    '<bool name="pref_default_value_file_list_show_hidden_files">false</bool>',
    '<bool name="pref_default_value_file_list_show_hidden_files">true</bool>',
)

# Use a distinct app name while retaining GPL attribution to Material Files.
for strings in (app / "src/main/res").glob("values*/strings.xml"):
    text = strings.read_text(encoding="utf-8")
    text2 = re.sub(
        r'<string name="app_name">.*?</string>',
        '<string name="app_name">ESStyle 文件管理器</string>',
        text,
        count=1,
        flags=re.S,
    )
    if text2 != text:
        strings.write_text(text2, encoding="utf-8")

manifest = app / "src/main/AndroidManifest.xml"
manifest_text = manifest.read_text(encoding="utf-8")
launcher_filter = '''            <intent-filter>\n                <action android:name="android.intent.action.MAIN" />\n                <category android:name="android.intent.category.LAUNCHER" />\n                <category android:name="android.intent.category.LEANBACK_LAUNCHER" />\n            </intent-filter>\n'''
if launcher_filter not in manifest_text:
    raise RuntimeError("Could not locate the upstream launcher intent-filter")
manifest_text = manifest_text.replace(launcher_filter, "", 1)
insert_before = '''        <activity\n            android:name="me.zhanghai.android.files.filelist.FileListActivity"'''
home_manifest = '''        <activity\n            android:name="me.zhanghai.android.files.esstyle.EsHomeActivity"\n            android:exported="true"\n            android:label="@string/app_name">\n            <intent-filter>\n                <action android:name="android.intent.action.MAIN" />\n                <category android:name="android.intent.category.LAUNCHER" />\n                <category android:name="android.intent.category.LEANBACK_LAUNCHER" />\n            </intent-filter>\n        </activity>\n\n        <activity\n            android:name="me.zhanghai.android.files.esstyle.EsDocumentTreeGrantActivity"\n            android:exported="false"\n            android:label="@string/app_name" />\n\n'''
if insert_before not in manifest_text:
    raise RuntimeError("Could not locate FileListActivity in manifest")
manifest.write_text(manifest_text.replace(insert_before, home_manifest + insert_before, 1), encoding="utf-8")

src_dir = app / "src/main/java/me/zhanghai/android/files/esstyle"
src_dir.mkdir(parents=True, exist_ok=True)

home_source = r'''/*
 * ESStyleFileManager customization layer.
 * Derived from Material Files under GPL-3.0; no ES File Explorer proprietary code or artwork used.
 */
package me.zhanghai.android.files.esstyle

import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Environment
import android.os.StatFs
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java8.nio.file.Paths
import me.zhanghai.android.files.app.AppActivity
import me.zhanghai.android.files.filelist.FileListActivity
import me.zhanghai.android.files.ftpserver.FtpServerActivity
import me.zhanghai.android.files.settings.SettingsActivity
import me.zhanghai.android.files.storage.AddStorageDialogActivity

class EsHomeActivity : AppActivity() {

    private val accent = Color.rgb(45, 137, 239)
    private val subtle = Color.rgb(245, 247, 250)
    private val textPrimary = Color.rgb(35, 39, 47)
    private val textSecondary = Color.rgb(105, 111, 121)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "ESStyle 文件管理器"
        setContentView(buildHome())
    }

    private fun buildHome(): View {
        val scroll = ScrollView(this)
        scroll.isFillViewport = true
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(14), dp(14), dp(24))
        }
        scroll.addView(root, LinearLayout.LayoutParams(-1, -2))

        root.addView(storageCard())
        addSectionTitle(root, "分类")
        addTileRow(root,
            Tile("图片", "IMG") { openPublic(Environment.DIRECTORY_PICTURES) },
            Tile("音乐", "MUSIC") { openPublic(Environment.DIRECTORY_MUSIC) },
            Tile("视频", "VIDEO") { openPublic(Environment.DIRECTORY_MOVIES) },
            Tile("文档", "DOC") { openPublic(Environment.DIRECTORY_DOCUMENTS) }
        )
        addTileRow(root,
            Tile("下载", "DOWN") { openPublic(Environment.DIRECTORY_DOWNLOADS) },
            Tile("应用", "APK") { openFullManager() },
            Tile("压缩包", "ZIP") { openFullManager() },
            Tile("最近文件", "REC") { openFullManager() }
        )

        addSectionTitle(root, "本地存储")
        root.addView(actionRow("内部存储", "浏览手机全部可访问文件") { openInternalStorage() })
        root.addView(actionRow("Android / data", "无 Root：通过系统文档授权访问；授权后会加入侧栏") {
            grantAndroidTree("data")
        })
        root.addView(actionRow("Android / obb", "无 Root：通过系统文档授权访问；授权后会加入侧栏") {
            grantAndroidTree("obb")
        })
        root.addView(actionRow("完整文件管理", "进入 Material Files 文件列表、收藏、书签与存储侧栏") {
            openFullManager()
        })

        addSectionTitle(root, "网络与工具")
        root.addView(actionRow("网络存储", "SMB / SFTP / FTP / WebDAV / 文档树") {
            startActivity(Intent(this, AddStorageDialogActivity::class.java))
        })
        root.addView(actionRow("FTP 服务器", "把手机文件通过局域网 FTP 分享给其它设备") {
            startActivity(Intent(this, FtpServerActivity::class.java))
        })
        root.addView(actionRow("设置", "显示方式、隐藏文件、主题、Root/Shizuku（均为可选）") {
            startActivity(Intent(this, SettingsActivity::class.java))
        })

        val footer = TextView(this).apply {
            text = "基于 Material Files v1.7.4（GPL-3.0）重新设计。ES 仅作为交互参考，不包含其闭源代码或商标素材。"
            setTextColor(textSecondary)
            textSize = 12f
            setPadding(dp(4), dp(22), dp(4), 0)
        }
        root.addView(footer)
        return scroll
    }

    private fun storageCard(): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(16), dp(18), dp(16))
            background = rounded(accent, 16f)
        }
        val title = TextView(this).apply {
            text = "本地存储"
            setTextColor(Color.WHITE)
            textSize = 19f
        }
        card.addView(title)

        val storage = Environment.getExternalStorageDirectory()
        val stat = StatFs(storage.absolutePath)
        val total = stat.totalBytes.coerceAtLeast(1L)
        val free = stat.availableBytes
        val used = (total - free).coerceAtLeast(0L)
        val percent = ((used * 100L) / total).toInt().coerceIn(0, 100)
        val detail = TextView(this).apply {
            text = "已用 ${formatSize(used)} / ${formatSize(total)}    可用 ${formatSize(free)}"
            setTextColor(Color.argb(220, 255, 255, 255))
            textSize = 13f
            setPadding(0, dp(7), 0, dp(9))
        }
        card.addView(detail)
        val progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            this.progress = percent
        }
        card.addView(progress, LinearLayout.LayoutParams(-1, dp(8)))
        card.setOnClickListener { openInternalStorage() }
        return card
    }

    private fun addSectionTitle(parent: LinearLayout, text: String) {
        parent.addView(TextView(this).apply {
            this.text = text
            setTextColor(textPrimary)
            textSize = 16f
            setPadding(dp(3), dp(22), 0, dp(10))
        })
    }

    private data class Tile(val label: String, val badge: String, val action: () -> Unit)

    private fun addTileRow(parent: LinearLayout, vararg tiles: Tile) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            weightSum = tiles.size.toFloat()
        }
        for (tile in tiles) {
            val cell = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                setPadding(dp(4), dp(10), dp(4), dp(10))
                isClickable = true
                isFocusable = true
                background = rounded(subtle, 12f)
                setOnClickListener { tile.action() }
            }
            val badge = TextView(this).apply {
                text = tile.badge
                setTextColor(accent)
                textSize = 11f
                gravity = Gravity.CENTER
                background = rounded(Color.WHITE, 9f)
                setPadding(dp(8), dp(7), dp(8), dp(7))
            }
            cell.addView(badge)
            cell.addView(TextView(this).apply {
                text = tile.label
                setTextColor(textPrimary)
                textSize = 13f
                gravity = Gravity.CENTER
                setPadding(0, dp(8), 0, 0)
            })
            val lp = LinearLayout.LayoutParams(0, dp(86), 1f).apply {
                marginStart = dp(3)
                marginEnd = dp(3)
            }
            row.addView(cell, lp)
        }
        parent.addView(row, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(7) })
    }

    private fun actionRow(title: String, subtitle: String, action: () -> Unit): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(13), dp(16), dp(13))
            background = rounded(subtle, 12f)
            isClickable = true
            isFocusable = true
            setOnClickListener { action() }
            addView(TextView(this@EsHomeActivity).apply {
                text = title
                setTextColor(textPrimary)
                textSize = 15f
            })
            addView(TextView(this@EsHomeActivity).apply {
                text = subtitle
                setTextColor(textSecondary)
                textSize = 12f
                setPadding(0, dp(4), 0, 0)
            })
        }.also {
            it.layoutParams = LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(8) }
        }
    }

    private fun openInternalStorage() {
        runCatching {
            val path = Paths.get(Environment.getExternalStorageDirectory().absolutePath)
            startActivity(FileListActivity.createViewIntent(path))
        }.onFailure { openFullManager() }
    }

    private fun openPublic(type: String) {
        runCatching {
            val path = Paths.get(Environment.getExternalStoragePublicDirectory(type).absolutePath)
            startActivity(FileListActivity.createViewIntent(path))
        }.onFailure {
            Toast.makeText(this, "无法直接打开该分类，已进入完整文件管理", Toast.LENGTH_SHORT).show()
            openFullManager()
        }
    }

    private fun openFullManager() {
        startActivity(Intent(this, FileListActivity::class.java))
    }

    private fun grantAndroidTree(target: String) {
        startActivity(Intent(this, EsDocumentTreeGrantActivity::class.java).putExtra("target", target))
    }

    private fun rounded(color: Int, radiusDp: Float): GradientDrawable = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radiusDp.toInt()).toFloat()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()

    private fun formatSize(bytes: Long): String {
        val gb = bytes / 1073741824.0
        return if (gb >= 1.0) String.format("%.1f GB", gb) else String.format("%.0f MB", bytes / 1048576.0)
    }
}
'''
(src_dir / "EsHomeActivity.kt").write_text(home_source, encoding="utf-8")

grant_source = r'''/*
 * SAF shortcut for Android/data and Android/obb.
 * The system DocumentsUI decides which directories can be granted on each Android/OEM build.
 */
package me.zhanghai.android.files.esstyle

import android.net.Uri
import android.os.Bundle
import android.provider.DocumentsContract
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import me.zhanghai.android.files.app.AppActivity
import me.zhanghai.android.files.file.asDocumentTreeUriOrNull
import me.zhanghai.android.files.file.takePersistablePermission
import me.zhanghai.android.files.storage.DocumentTree
import me.zhanghai.android.files.storage.Storages

class EsDocumentTreeGrantActivity : AppActivity() {

    private val launcher = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { result ->
        val treeUri = result?.asDocumentTreeUriOrNull()
        if (treeUri != null) {
            runCatching {
                treeUri.takePersistablePermission()
                Storages.addOrReplace(DocumentTree(null, null, treeUri))
            }.onSuccess {
                Toast.makeText(this, "授权成功，目录已加入文件管理侧栏", Toast.LENGTH_LONG).show()
            }.onFailure {
                Toast.makeText(this, "保存目录授权失败：${it.message ?: "未知错误"}", Toast.LENGTH_LONG).show()
            }
        } else if (result != null) {
            Toast.makeText(this, "系统没有返回可持久化的目录授权", Toast.LENGTH_LONG).show()
        }
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState != null) return
        val target = intent.getStringExtra("target").takeUnless { it.isNullOrBlank() } ?: "data"
        val initialUri = initialUriFor(target)
        runCatching { launcher.launch(initialUri) }
            .onFailure {
                Toast.makeText(this, "无法打开系统目录授权器：${it.message ?: "未知错误"}", Toast.LENGTH_LONG).show()
                finish()
            }
    }

    private fun initialUriFor(target: String): Uri? = runCatching {
        DocumentsContract.buildDocumentUri(
            "com.android.externalstorage.documents",
            "primary:Android/$target"
        )
    }.getOrNull()
}
'''
(src_dir / "EsDocumentTreeGrantActivity.kt").write_text(grant_source, encoding="utf-8")

print("Customization applied successfully")
