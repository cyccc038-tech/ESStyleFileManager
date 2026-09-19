package com.cyccc038.esauthprobe

import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.iadb.Iadb

class MainActivity : Activity() {
    private val requestCode = 5201
    private lateinit var status: TextView

    private val binderReceivedListener = Iadb.OnBinderReceivedListener {
        runOnUiThread { refreshStatus(false) }
    }

    private val binderDeadListener = Iadb.OnBinderDeadListener {
        runOnUiThread {
            status.text = "iAdb 服务已断开。请打开 iAdb 并确认无线调试仍在运行。"
        }
    }

    private val permissionListener =
        Iadb.OnRequestPermissionResultListener { code, grantResult ->
            if (code == requestCode) {
                runOnUiThread {
                    if (grantResult == PackageManager.PERMISSION_GRANTED) {
                        status.text = "授权成功\n\n第一步通过：本应用已经获得 iAdb 调试服务授权。"
                    } else {
                        status.text = "授权未通过。请在 iAdb 的授权窗口中允许本应用。"
                    }
                }
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val density = resources.displayMetrics.density
        fun dp(v: Int) = (v * density).toInt()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(24), dp(36), dp(24), dp(24))
        }

        root.addView(TextView(this).apply {
            text = "ES V5.2 · Android 16 授权测试"
            textSize = 22f
            setTypeface(typeface, Typeface.BOLD)
        }, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))

        root.addView(TextView(this).apply {
            text = "这一步只验证一次性 iAdb 授权，不读取、修改或删除任何文件。"
            textSize = 15f
            setPadding(0, dp(18), 0, dp(18))
        })

        status = TextView(this).apply {
            textSize = 16f
            setPadding(dp(14), dp(14), dp(14), dp(14))
        }
        root.addView(status, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))

        root.addView(Button(this).apply {
            text = "检查 / 请求授权"
            setOnClickListener { refreshStatus(true) }
        }, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))

        root.addView(TextView(this).apply {
            text = "使用前：安装并打开 iAdb，在开发者选项中开启“无线调试”，先让 iAdb 自己连接成功。"
            textSize = 14f
            setPadding(0, dp(20), 0, 0)
        })

        setContentView(root)

        Iadb.addBinderReceivedListener(binderReceivedListener)
        Iadb.addBinderDeadListener(binderDeadListener)
        Iadb.addRequestPermissionResultListener(permissionListener)
        refreshStatus(false)
    }

    private fun refreshStatus(requestIfNeeded: Boolean) {
        try {
            if (!Iadb.pingBinder()) {
                status.text = "未检测到 iAdb 服务。\n\n请先打开 iAdb，并完成无线调试连接。"
                return
            }

            if (Iadb.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                status.text = "授权成功\n\niAdb 服务在线，应用权限已经授予。"
                return
            }

            if (requestIfNeeded) {
                status.text = "正在请求 iAdb 授权…"
                Iadb.requestPermission(requestCode)
            } else {
                status.text = "iAdb 服务在线，但本应用尚未授权。\n\n点击“检查 / 请求授权”。"
            }
        } catch (t: Throwable) {
            status.text = "授权检测失败：${t.javaClass.simpleName}\n${t.message ?: ""}"
        }
    }

    override fun onDestroy() {
        try {
            Iadb.removeBinderReceivedListener(binderReceivedListener)
            Iadb.removeBinderDeadListener(binderDeadListener)
            Iadb.removeRequestPermissionResultListener(permissionListener)
        } catch (_: Throwable) {
        }
        super.onDestroy()
    }
}
