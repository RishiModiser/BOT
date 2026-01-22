# PyInstaller Build Instructions for Humanex v4.0

## 🎯 Overview

This guide explains how to build Humanex v4.0 into a single-click executable (.exe) for Windows using PyInstaller.

## 📋 Prerequisites

- **Python 3.11+** installed on Windows
- **All dependencies** installed (`pip install -r requirements.txt`)
- **PyInstaller** installed (`pip install pyinstaller`)
- **Playwright browsers** installed (`playwright install chromium`)

## 🚀 Quick Build

### Using the Batch Script (Recommended)

Simply run the provided batch script:

```cmd
build_exe.bat
```

This will:
1. Check/install PyInstaller
2. Clean previous builds
3. Build the executable
4. Clean up artifacts

The final `.exe` will be in the `dist/` folder.

### Manual Build

```cmd
pyinstaller --onefile --windowed --name=Humanex Humanex_v4.0.py
```

## 🔧 Detailed Build Options

### Basic Build Command

```cmd
pyinstaller Humanex_v4.0.py
```

This creates:
- `build/` - Temporary build files
- `dist/` - Output folder with executable
- `Humanex.spec` - Build specification file

### Production Build Command

```cmd
pyinstaller ^
    --onefile ^
    --windowed ^
    --name=Humanex ^
    --icon=humanex.ico ^
    --add-data="configs;configs" ^
    --add-data="scripts;scripts" ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=playwright ^
    --hidden-import=playwright.sync_api ^
    Humanex_v4.0.py
```

### Option Explanations

| Option | Description | Why Use It |
|--------|-------------|------------|
| `--onefile` | Package into single .exe | Easier distribution |
| `--windowed` | No console window | Clean GUI experience |
| `--name=Humanex` | Output filename | Better branding |
| `--icon=humanex.ico` | Application icon | Professional look |
| `--add-data` | Include folders | Bundle configs/scripts |
| `--hidden-import` | Force include modules | Fix import errors |
| `--clean` | Clean PyInstaller cache | Fresh build |
| `--noconfirm` | Overwrite without prompt | Automated builds |

## 📦 Advanced Build Configuration

### Creating a Spec File

Generate a customizable spec file:

```cmd
pyi-makespec --onefile --windowed Humanex_v4.0.py
```

Edit `Humanex.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['Humanex_v4.0.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('configs', 'configs'),
        ('scripts', 'scripts'),
        ('proxies.txt', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'playwright',
        'playwright.sync_api',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Humanex',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='humanex.ico',
)
```

Build using spec file:

```cmd
pyinstaller Humanex.spec
```

## 🎨 Adding an Icon

### Creating the Icon

1. Get a 256x256 PNG image
2. Convert to ICO format:
   - Online: [favicon.io](https://favicon.io/)
   - Tool: ImageMagick `convert logo.png -define icon:auto-resize=256,128,64,48,32,16 humanex.ico`

3. Place `humanex.ico` in project root

4. Build with icon:
   ```cmd
   pyinstaller --onefile --windowed --icon=humanex.ico --name=Humanex Humanex_v4.0.py
   ```

## 🌐 Bundling Playwright Browsers

### Option 1: User Installs Browsers

User must run after installing:
```cmd
playwright install chromium
```

**Pros**: Smaller .exe size
**Cons**: Extra step for users

### Option 2: Bundle Browsers (Advanced)

1. Install browsers locally:
   ```cmd
   playwright install chromium
   ```

2. Find browser location:
   ```cmd
   python -c "import os; print(os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'Default location'))"
   ```

3. Add to spec file:
   ```python
   datas=[
       ('ms-playwright', 'ms-playwright'),
   ]
   ```

4. Build:
   ```cmd
   pyinstaller Humanex.spec
   ```

**Pros**: Fully portable
**Cons**: ~200MB larger .exe

## 🔒 Code Protection

### UPX Compression

Compress the executable:

```cmd
pyinstaller --onefile --windowed --upx-dir="C:\upx" Humanex_v4.0.py
```

Download UPX from [upx.github.io](https://upx.github.io/)

### Obfuscation (Optional)

For additional protection:

1. Install PyArmor:
   ```cmd
   pip install pyarmor
   ```

2. Obfuscate code:
   ```cmd
   pyarmor obfuscate Humanex_v4.0.py
   ```

3. Build obfuscated version:
   ```cmd
   pyinstaller --onefile --windowed dist/Humanex_v4.0.py
   ```

## 🧪 Testing the Build

### Test Locally

```cmd
dist\Humanex.exe
```

Check for:
- ✅ Application launches without errors
- ✅ GUI displays correctly
- ✅ License window appears
- ✅ Can load proxies
- ✅ Can add URLs
- ✅ Bot starts successfully
- ✅ Logs display properly

### Test on Clean Machine

Test on Windows machine without Python installed:

1. Copy `Humanex.exe` to clean machine
2. Copy `proxies.txt` (if needed)
3. Double-click `Humanex.exe`
4. Verify functionality

## 📊 Build Output Analysis

### Check Build Size

```cmd
dir dist\Humanex.exe
```

Typical sizes:
- **Without browsers**: 50-80 MB
- **With browsers**: 250-300 MB

### Analyze Dependencies

```cmd
pyi-archive_viewer dist\Humanex.exe
```

Commands in viewer:
- `l` - List all files
- `x filename` - Extract file
- `q` - Quit

## 🐛 Common Build Issues

### Issue: "Failed to execute script"

**Solution**: Add missing imports to spec file
```python
hiddenimports=['missing_module']
```

### Issue: "PyQt6 DLL load failed"

**Solution**: Update PyQt6
```cmd
pip install --upgrade PyQt6
```

### Issue: "Playwright browsers not found"

**Solution**: User must install browsers:
```cmd
playwright install chromium
```

Or bundle browsers in build (see above).

### Issue: ".exe is too large"

**Solutions**:
- Use `--onefile` mode
- Enable UPX compression
- Exclude unnecessary modules:
  ```python
  excludes=['tkinter', 'matplotlib', 'numpy']
  ```

### Issue: "Antivirus flags .exe"

**Solutions**:
- Sign the executable (code signing certificate)
- Submit to antivirus vendors for whitelisting
- Use `--clean` to ensure fresh build
- Build on different machine/VM

## 📝 Build Checklist

Before distributing:

- [ ] All dependencies installed
- [ ] Code tested and working
- [ ] Build completes without errors
- [ ] .exe launches successfully
- [ ] GUI displays correctly
- [ ] Core features work (load proxies, start bot, etc.)
- [ ] Tested on clean Windows machine
- [ ] Icon displays properly
- [ ] File size is reasonable
- [ ] README.md included
- [ ] License information added
- [ ] Version number updated

## 🚀 Distribution

### Files to Include

Create a distribution package with:

```
Humanex_v4.0_Release/
├── Humanex.exe                    # Main executable
├── README.md                      # User documentation
├── INSTALLATION.md                # Setup guide
├── proxies.txt.example            # Proxy format example
├── configs/
│   └── sample_settings.json       # Config template
├── scripts/
│   ├── sample_script.json         # Example RPA script
│   └── advanced_ecommerce.json    # Advanced example
└── LICENSE.txt                    # License information
```

### Create ZIP

```cmd
powershell Compress-Archive -Path dist\Humanex.exe, README.md, INSTALLATION.md, proxies.txt, configs\, scripts\ -DestinationPath Humanex_v4.0_Release.zip
```

### Release Notes Template

```markdown
# Humanex v4.0 - JARVIS Edition

## 🎉 What's New
- ✨ PyQt6 GUI with JARVIS-style dark theme
- 🤖 Visual RPA Script Builder
- ⚡ Enhanced performance and stability
- 🔒 Improved anti-detection features
- 📊 Real-time monitoring and logging

## 📥 Installation
1. Extract ZIP to folder
2. (Optional) Run `playwright install chromium`
3. Edit `proxies.txt` with your proxies
4. Double-click `Humanex.exe`

## 🆕 Changes Since v3.x
- Migrated to PyQt6
- Added RPA Script Builder
- Improved GUI design
- Better proxy management
- Enhanced logging system

## ⚠️ Requirements
- Windows 10/11 (64-bit)
- No Python installation required
- Internet connection for license verification
- Valid license key

## 📧 Support
- Issues: github.com/RishiModiser/BOT/issues
- License: [contact info]
```

## 🔄 Automated Build Script

Create `build_and_package.bat`:

```batch
@echo off
echo Building Humanex v4.0...

REM Clean
rmdir /s /q build dist
del Humanex.spec

REM Build
pyinstaller --onefile --windowed --name=Humanex --icon=humanex.ico Humanex_v4.0.py

REM Package
if exist dist\Humanex.exe (
    echo Creating release package...
    mkdir release
    copy dist\Humanex.exe release\
    copy README.md release\
    copy INSTALLATION.md release\
    copy proxies.txt release\proxies.txt.example
    xcopy /e /i configs release\configs
    xcopy /e /i scripts release\scripts
    
    echo Compressing...
    powershell Compress-Archive -Force -Path release\* -DestinationPath Humanex_v4.0_Release.zip
    
    echo Done! Release package: Humanex_v4.0_Release.zip
) else (
    echo Build failed!
)
```

## 📚 Additional Resources

- **PyInstaller Docs**: https://pyinstaller.org/en/stable/
- **PyQt6 Docs**: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- **Playwright Docs**: https://playwright.dev/python/
- **UPX**: https://upx.github.io/
- **Code Signing**: https://learn.microsoft.com/en-us/windows/win32/seccrypto/cryptography-tools

## ✅ Final Check

Your build is ready for distribution when:

1. ✅ .exe runs on your machine
2. ✅ .exe runs on clean machine (no Python)
3. ✅ GUI displays correctly
4. ✅ Core features work
5. ✅ No console window appears
6. ✅ Icon displays properly
7. ✅ File size is acceptable
8. ✅ Antivirus doesn't flag it (or you've signed it)
9. ✅ Documentation is complete
10. ✅ License terms are clear

---

**Happy Building!** 🏗️ **Now you can distribute Humanex v4.0 as a single-click desktop app!** 🚀
