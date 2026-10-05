[app]

# ---- identity ---------------------------------------------------------
title = Task Manager
package.name = taskmanager
package.domain = org.taskmanager
version = 1.0.0

# ---- sources ----------------------------------------------------------
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt
source.include_patterns = assets/*,assets/fonts/*
source.exclude_dirs = tests,bin,.buildozer,.github,.git,__pycache__,venv,.venv
source.exclude_patterns = *.md,.gitignore,requirements.txt,*.apk

# ---- dependencies -----------------------------------------------------
# python-for-android installs these into the APK.
# arabic-reshaper + python-bidi (+six) are pure Python and only improve how
# Arabic/Hebrew task titles are DISPLAYED. python-bidi is pinned to 0.4.2
# because newer releases need a Rust toolchain that python-for-android lacks.
# The app also runs without them, so you may delete those three entries if a
# build ever fails because of them.
requirements = python3,kivy==2.3.0,arabic-reshaper==3.0.0,python-bidi==0.4.2,six

# ---- display ----------------------------------------------------------
orientation = portrait
fullscreen = 0

# ---- android ----------------------------------------------------------
# No permissions: tasks are saved in the app's private storage folder.
android.permissions =
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.debug_artifact = apk
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
