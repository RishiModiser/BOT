# Humanex v4.0 - Installation & Setup Guide

## 📋 Prerequisites

Before installing Humanex v4.0, ensure you have:

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.11 or higher (3.12 also supported)
- **RAM**: Minimum 4GB (8GB+ recommended for multiple concurrent sessions)
- **Disk Space**: At least 2GB free space (for Playwright browsers)
- **Internet Connection**: Required for initial setup and proxy validation

## 🔧 Step-by-Step Installation

### Option 1: Run from Source (Recommended for Development)

#### 1. Install Python

Download and install Python from [python.org](https://www.python.org/downloads/)

**Important**: During installation, check "Add Python to PATH"

Verify installation:
```cmd
python --version
```

#### 2. Clone or Download Repository

```cmd
git clone https://github.com/RishiModiser/BOT.git
cd BOT
```

Or download ZIP and extract to a folder.

#### 3. Create Virtual Environment (Recommended)

```cmd
python -m venv venv
venv\Scripts\activate
```

#### 4. Install Dependencies

```cmd
pip install -r requirements.txt
```

This will install:
- PyQt6 (GUI framework)
- Playwright (browser automation)
- Requests (HTTP library)

#### 5. Install Playwright Browsers

```cmd
playwright install chromium
```

**Note**: This downloads ~200MB of browser files.

#### 6. Prepare Configuration Files

Create/edit these files in the root directory:

**proxies.txt** (one proxy per line):
```
123.456.789.012:8080:username:password
98.765.432.101:3128
socks5://user:pass@proxy.example.com:1080
```

**user_agents.txt** (optional, one per line):
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit...
```

#### 7. Run the Application

```cmd
python Humanex_v4.0.py
```

### Option 2: Build Standalone EXE (Recommended for Distribution)

#### 1. Complete Steps 1-5 from Option 1

#### 2. Install PyInstaller

```cmd
pip install pyinstaller
```

#### 3. Build the Executable

**Windows (using batch script)**:
```cmd
build_exe.bat
```

**Manual build**:
```cmd
pyinstaller --onefile --windowed --name=Humanex Humanex_v4.0.py
```

#### 4. Locate the EXE

The executable will be in `dist\Humanex.exe`

#### 5. Distribute

Copy `Humanex.exe` and these files to target machine:
- `proxies.txt`
- `configs/` folder
- `scripts/` folder
- `ms-playwright/` folder (if bundling browsers)

**Double-click Humanex.exe to run!**

## ⚙️ Configuration

### Directory Structure After Installation

```
BOT/
├── Humanex_v4.0.py           # Main application
├── proxies.txt                # Your proxy list
├── user_agents.txt            # (Optional) User agent list
├── cookies.json               # (Optional) Cookies file
├── requirements.txt           # Python dependencies
├── build_exe.bat              # Build script
├── README.md                  # Documentation
├── configs/                   # Configuration files
│   └── sample_settings.json   # Settings template
├── scripts/                   # RPA scripts
│   ├── sample_script.json
│   └── advanced_ecommerce.json
└── logs/                      # Application logs
    └── humanex_YYYYMMDD_HHMMSS.log
```

### Environment Variables (Optional)

Set these for advanced configuration:

```cmd
set PLAYWRIGHT_BROWSERS_PATH=C:\ms-playwright
set PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
```

## 🎮 First Run Setup

### 1. Launch Application

```cmd
python Humanex_v4.0.py
```

Or double-click `Humanex.exe`

### 2. Enter License Key

When prompted, enter your license key:
```
ASAD-2025-PRO
```

Contact your license provider if you don't have a key.

### 3. Configure Website Details

Go to **🌐 Website Details** tab:

1. Click **➕ Add URL**
2. Enter target URL (e.g., `https://example.com`)
3. Set stay time in milliseconds (e.g., `30000` = 30 seconds)
4. Add more URLs as needed
5. (Optional) Load **User Agents** file
6. (Optional) Load **Cookies** file

### 4. Configure Traffic Settings

Go to **⚙️ Traffic Settings** tab:

1. Set **Concurrent Profiles** (e.g., `5` for 5 parallel sessions)
2. Set **Device Distribution**:
   - Desktop: `70%`
   - Mobile: `30%`
3. Choose **Visit Type** (Direct, Google, Facebook, etc.)
4. Enable/disable **Headless Mode**
5. Enable **Human-like Scrolling** (recommended)

### 5. Load Proxies

Go to **🔒 Proxy Settings** tab:

1. Click **📁 Load Proxy List**
2. Select your `proxies.txt` file
3. Verify proxy count in status display

### 6. Start Bot

1. Click **🚀 START BOT** button in sidebar
2. Monitor progress in **📋 Logs & Status** tab
3. Watch **Active Sessions** and **Left Sessions** counters
4. Click **⏹ STOP BOT** to halt execution

## 🤖 Using RPA Script Builder

### Creating a Script

1. Go to **🤖 RPA Script Builder** tab
2. Click action buttons to add steps:
   - **New Page** - Opens new browser tab
   - **Navigate** - Goes to specified URL
   - **Wait** - Pauses for specified duration
   - **Scroll** - Scrolls page (human-like)
   - **Click** - Clicks element (CSS selector)
   - **Input Text** - Fills form field
   - **Refresh Page** - Reloads current page
   - **Go Back** - Browser back button
   - **Close Others** - Closes all tabs except current

### Managing Steps

- **↑ Move Up** - Move selected step up
- **↓ Move Down** - Move selected step down
- **🗑 Delete** - Remove selected step
- **💾 Save Script** - Export to JSON file
- **📂 Load Script** - Import from JSON file

### Example Script

```json
{
  "name": "My Shopping Bot",
  "actions": [
    {
      "type": "navigate",
      "config": {"url": "https://shop.com", "timeout": 30000}
    },
    {
      "type": "wait",
      "config": {"duration": 2000}
    },
    {
      "type": "scrollPage",
      "config": {
        "scrollType": "position",
        "position": "middle"
      }
    }
  ]
}
```

## 🔍 Advanced Features

### Keyword Search Mode

Simulates Google search followed by clicking your domain in results:

1. Enable **"Enable Keyword Search"** in Traffic Settings
2. Enter **Main URL**: `https://yourdomain.com`
3. Enter **Keywords**: `keyword1, keyword2, keyword3`
4. Set **Stay Time**: `30000` (30 seconds)
5. Bot will:
   - Search keyword on Google
   - Find your domain in results
   - Click and browse your site
   - Perform human-like interactions

### Cookie Management

Import cookies to maintain logged-in sessions:

**JSON Format**:
```json
{
  "cookies": [
    {
      "name": "session_id",
      "value": "abc123xyz",
      "domain": ".example.com",
      "path": "/",
      "secure": true
    }
  ]
}
```

**Netscape Format**:
```
# Netscape HTTP Cookie File
.example.com	TRUE	/	FALSE	1735689600	session_id	abc123xyz
```

### User Agent Rotation

Create `user_agents.txt` with one user agent per line:

```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

Bot will randomly select one user agent per session.

## 🐛 Troubleshooting

### Application Won't Start

**Error**: "No module named 'PyQt6'"
```cmd
pip install PyQt6
```

**Error**: "No module named 'playwright'"
```cmd
pip install playwright
playwright install chromium
```

**Error**: "License verification failed"
- Check internet connection
- Verify license key is correct
- Contact license provider

### Proxy Issues

**Error**: "Proxy connection failed"
- Verify proxy format: `host:port:user:pass`
- Test proxy manually: `curl -x http://user:pass@host:port https://api.ipify.org`
- Check proxy is online and not blocked

**Error**: "Proxy authentication failed"
- Verify username and password
- Check for special characters (escape if needed)

### Browser Issues

**Error**: "Playwright browser not found"
```cmd
playwright install chromium
```

**Error**: "Browser launch failed"
- Check antivirus isn't blocking
- Try disabling headless mode
- Run as administrator (if necessary)

### Performance Issues

**Slow execution**:
- Reduce **Concurrent Profiles**
- Increase **Stay Time** to reduce frequency
- Use faster proxies

**High memory usage**:
- Reduce concurrent sessions
- Enable **Headless Mode**
- Close other applications

### CAPTCHA Problems

**Google CAPTCHA appears**:
- Use residential proxies (not datacenter)
- Reduce request frequency
- Add longer delays between actions
- Enable all anti-detection features

## 📞 Support

### Documentation
- **README.md** - Feature overview and quick start
- **This file** - Detailed installation and setup
- **configs/sample_settings.json** - Configuration reference

### Community
- **GitHub Issues**: https://github.com/RishiModiser/BOT/issues
- **License Support**: Contact your provider

### Logs
Check `logs/` folder for detailed error messages and session history.

## 🔄 Updating

### Update from Source

```cmd
cd BOT
git pull origin main
pip install -r requirements.txt --upgrade
```

### Update Standalone EXE

Download latest version from release page and replace `Humanex.exe`

## ✅ Verification

After installation, verify everything works:

1. **Start application** - No errors on launch
2. **Load proxies** - Status shows proxy count
3. **Add URL** - URL table accepts entries
4. **Start bot** - Sessions begin executing
5. **Check logs** - Green messages appear
6. **Stop bot** - Cleanly halts all sessions

## 🎉 You're Ready!

Humanex v4.0 is now installed and configured. Happy automating! 🚀

---

**Need Help?** Open an issue on GitHub or contact support.
