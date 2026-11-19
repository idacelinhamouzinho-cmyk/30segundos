[app]
title = 30 Seconds
package.name = jogo30seconds
package.domain = org.meusjogos

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,ttf

version = 1.0
requirements = python3,kivy==2.3.0

icon.filename = icon.png
presplash.filename = presplash.png
android.presplash_color = #0D1126

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
