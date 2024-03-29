# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

added_files = [
    ( 'imgs/default_imgs/*', 'imgs/default_imgs' ),
    ( 'src/qt_designer_file/*', 'src/qt_designer_file' ),
    ( 'src/yolov4/data/*', 'src/yolov4/data' ),
    ( 'src/yolov4/cfg/*', 'src/yolov4/cfg' ),
    ( 'src/yolov4/weights/*', 'src/yolov4/weights' ),
    ( 'src/obj_detector/weights/*', 'src/obj_detector/weights' ),
    ( 'src/obj_detector/cfg/*', 'src/obj_detector/cfg' ),
    ( 'src/yolov3/models/*.yaml', 'src/yolov3/models' ),
    ( 'src/yolox/weights/*', 'src/yolox/weights' ),
    ( 'src/detr/detr-r50-e632da11.pth', 'src/detr' ),
    ( 'src/detr/datasets/*', 'src/detr/datasets' ),
    ( 'src/cae/model/model_yt_small_final.state', 'src/cae/model' ),
    ( 'src/mtcnn/weights/*', 'src/mtcnn/weights'),
    ( 'default_aug.txt', '.')
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=['skimage.filters.edges'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

splash = Splash(
    'imgs/Qt_logo_2016.svg.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    splash.binaries,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)
