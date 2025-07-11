import PyInstaller.__main__
import os
import subprocess

# 获取当前 Git 标签作为版本号
def get_version():
    try:
        # 获取最新的 Git 标签
        version = subprocess.check_output(['git', 'describe', '--tags', '--abbrev=0']).decode().strip()
        # 去除 'v' 前缀（如 v1.0.0 -> 1.0.0）
        if version.startswith('v'):
            version = version[1:]
        return version
    except subprocess.CalledProcessError:
        # 如果没有标签，默认使用 '0.0.0'
        return '0.0.0'

version = get_version()
exe_name = f'字体瘦身-v{version}'

PyInstaller.__main__.run([
    'app.py',
    f'--name={exe_name}',
    '--windowed',
    '--onefile',
    '--icon=font.ico',
    '--add-data=font.ico;.'
])