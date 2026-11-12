package com.sundroid.host.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

class SunDroidAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "SunDroidA11y"
        var instance: SunDroidAccessibilityService? = null
            private set

        fun isServiceRunning(): Boolean = instance != null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "SunDroid Accessibility Service connected.")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {
        Log.w(TAG, "SunDroid Accessibility Service interrupted.")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        Log.i(TAG, "SunDroid Accessibility Service destroyed.")
    }

    fun injectTap(x: Float, y: Float) {
        val path = Path().apply {
            moveTo(x, y)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 40))
            .build()

        dispatchGesture(gesture, null, null)
    }

    fun injectSwipe(startX: Float, startY: Float, endX: Float, endY: Float, durationMs: Long = 100) {
        val path = Path().apply {
            moveTo(startX, startY)
            lineTo(endX, endY)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
            .build()

        dispatchGesture(gesture, null, null)
    }

    fun injectGlobalAction(actionName: String): Boolean {
        return when (actionName.uppercase()) {
            "BACK" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "HOME" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "RECENTS" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "POWER" -> performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)
            "NOTIFICATIONS" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
            "QUICK_SETTINGS" -> performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS)
            else -> false
        }
    }

    fun injectText(text: String): Boolean {
        return try {
            val rootNode = rootInActiveWindow ?: return false
            val focusedNode = rootNode.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            if (focusedNode != null) {
                val currentText = focusedNode.text?.toString() ?: ""
                val newText = currentText + text
                val args = Bundle().apply {
                    putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
                }
                val success = focusedNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                focusedNode.recycle()
                rootNode.recycle()
                success
            } else {
                rootNode.recycle()
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error injecting text: ${e.message}")
            false
        }
    }

    fun injectBackspace(): Boolean {
        return try {
            val rootNode = rootInActiveWindow ?: return false
            val focusedNode = rootNode.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            if (focusedNode != null) {
                val currentText = focusedNode.text?.toString() ?: ""
                if (currentText.isNotEmpty()) {
                    val newText = currentText.dropLast(1)
                    val args = Bundle().apply {
                        putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
                    }
                    focusedNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                }
                focusedNode.recycle()
                rootNode.recycle()
                true
            } else {
                rootNode.recycle()
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error injecting backspace: ${e.message}")
            false
        }
    }
}
