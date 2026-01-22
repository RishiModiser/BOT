# Humanex v4.0 - JARVIS Edition 🤖

**Human-Based Traffic Simulator** - Professional Desktop Application for Windows

## 🌟 Features

### ✨ JARVIS-Style GUI
- **Dark Futuristic Theme** - Black/dark-blue gradient with neon cyan & electric blue accents
- **Glassmorphism Panels** - Modern, elegant UI with rounded cards
- **Animated JARVIS Panel** - AI Core visualization with pulsing effects
- **Smooth Transitions** - Professional hover effects and animations

### 🎯 Core Capabilities
- **Multi-Threaded Automation** - Run multiple sessions concurrently
- **Proxy Support** - HTTP, HTTPS, SOCKS5 with authentication
- **Device Emulation** - Desktop and Mobile (Android) profiles
- **Human-Like Behavior** - Natural scrolling, mouse movement, and timing
- **Anti-Detection** - Advanced fingerprint randomization and stealth techniques
- **Keyword Search** - Google search automation with result clicking
- **Cookie Management** - Import cookies in JSON or Netscape format
- **User Agent Rotation** - Custom user agent lists

### 🤖 RPA Script Builder
Visual automation script builder with:
- **Navigate** - Go to URLs
- **Wait** - Timed delays
- **Scroll** - Human-like page scrolling
- **Click** - Element interaction
- **Input Text** - Form filling
- **New Page** - Open new tabs
- **Refresh** - Reload pages
- **Go Back** - Browser navigation
- **Close Others** - Tab management

### 📊 Traffic Settings
- **Concurrent Profiles** - Control parallel sessions
- **Device Distribution** - Set Desktop/Mobile percentage
- **Visit Type** - Direct, Google, Facebook, YouTube, Yahoo, Bing
- **Browser Mode** - Visible or headless
- **Human Scrolling** - Realistic user behavior simulation

### 🔒 Proxy System
- **Multi-Format Support** - `http://host:port:user:pass`, `https://host:port`, `socks5://user:pass@host:port`
- **Rotation** - Automatic proxy cycling per profile
- **Validation** - Verify proxy connectivity before use
- **Status Display** - Real-time proxy health monitoring

### 📋 Real-Time Monitoring
- **Live Logs** - Color-coded console output with timestamps
- **Session Counters** - Active and remaining sessions
- **Status Indicators** - Running, Processing, Ready states
- **Progress Tracking** - Visual feedback for all operations

## 📁 Folder Structure

```
BOT/
├── Humanex_v4.0.py          # Main application file
├── proxies.txt               # Proxy list (one per line)
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── build_exe.bat             # Windows build script
├── .gitignore                # Git ignore rules
├── configs/                  # Configuration files
│   └── settings.json         # App settings (auto-generated)
├── scripts/                  # RPA script files
│   └── sample_script.json    # Example RPA script
└── logs/                     # Application logs
    └── humanex_YYYYMMDD_HHMMSS.log
```

## 🚀 Quick Start

### Prerequisites
- **Python 3.11** (recommended)
- **Windows 10/11** (required)
- **Playwright browsers** (installed automatically)

### Installation

1. **Clone or download this repository**
   ```bash
   git clone https://github.com/RishiModiser/BOT.git
   cd BOT
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Prepare your data**
   - Add proxies to `proxies.txt` (one per line)
   - (Optional) Prepare user agent list
   - (Optional) Prepare cookies file (JSON or Netscape format)

5. **Run the application**
   ```bash
   python Humanex_v4.0.py
   ```

6. **Enter license key** (if required)
   - Contact provider for license key
   - Enter key in activation window

## 🎮 How to Use

### Basic Workflow

1. **Launch Application**
   - Double-click `Humanex_v4.0.py` or run via command line
   - Enter license key when prompted

2. **Configure Website Details**
   - Go to "🌐 Website Details" tab
   - Click "➕ Add URL" to add target URLs
   - Set stay time in milliseconds for each URL
   - (Optional) Load user agents file
   - (Optional) Load cookies file

3. **Configure Traffic Settings**
   - Go to "⚙️ Traffic Settings" tab
   - Set **Concurrent Profiles** (parallel sessions)
   - Set **Device Distribution** (Desktop % / Mobile %)
   - Choose **Visit Type** (Direct, Google, etc.)
   - Enable/disable **Headless Mode**
   - Enable/disable **Human-like Scrolling**
   - (Optional) Configure **Keyword Search**

4. **Load Proxies**
   - Go to "🔒 Proxy Settings" tab
   - Click "📁 Load Proxy List"
   - Select your `proxies.txt` file
   - Verify proxy count in status display

5. **Start Bot**
   - Click "🚀 START BOT" button
   - Monitor logs in "📋 Logs & Status" tab
   - View active/remaining sessions in sidebar
   - Click "⏹ STOP BOT" to halt execution

### Advanced Features

#### RPA Script Builder

1. Go to "🤖 RPA Script Builder" tab
2. Click action buttons to add steps:
   - **Navigate** - Enter URL
   - **Wait** - Enter duration in ms
   - **Scroll** - Auto-configured for human-like scrolling
   - **Click** - Enter CSS selector
   - **Input Text** - Enter selector and text
3. Use **↑ Move Up** / **↓ Move Down** to reorder steps
4. Use **🗑 Delete** to remove steps
5. View live JSON preview
6. Click **💾 Save Script** to export
7. Click **📂 Load Script** to import

#### Keyword Search Mode

1. Enable **"Enable Keyword Search"** checkbox
2. Enter **Main URL** (target website)
3. Enter **Keywords** (comma-separated)
4. Set **Stay Time** (milliseconds)
5. Bot will:
   - Search each keyword on Google
   - Find and click your domain in results
   - Perform human-like browsing
   - Record session data

## 🔧 Building Standalone EXE

### Using PyInstaller

1. **Install PyInstaller**
   ```bash
   pip install pyinstaller
   ```

2. **Run build command**
   ```bash
   pyinstaller --onefile --windowed --name="Humanex" --icon=humanex.ico Humanex_v4.0.py
   ```

   Or use the provided batch script:
   ```bash
   build_exe.bat
   ```

3. **Locate the executable**
   - Find `Humanex.exe` in `dist/` folder
   - Copy to any Windows machine
   - **Double-click to run** - No Python required!

### Build Options Explained

- `--onefile` - Package everything into single .exe
- `--windowed` - No console window (GUI only)
- `--name="Humanex"` - Output filename
- `--icon=humanex.ico` - Application icon (optional)

### Important Notes

- First run may be slow (extracting files)
- Antivirus may flag (false positive - whitelist it)
- Playwright browsers must be bundled separately or installed on target machine
- For distribution, include `ms-playwright` folder with browsers

## 📝 Configuration Files

### proxies.txt Format

```
# HTTP proxy with authentication
123.456.789.012:8080:username:password

# HTTPS proxy without authentication
98.765.432.101:3128

# SOCKS5 proxy with authentication
socks5://user:pass@proxy.example.com:1080
```

### User Agents File Format

```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit...
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...
```

### Cookies File Format (JSON)

```json
{
  "cookies": [
    {
      "name": "session_id",
      "value": "abc123",
      "domain": ".example.com",
      "path": "/",
      "secure": true,
      "httpOnly": true,
      "sameSite": "Lax"
    }
  ]
}
```

## 🛡️ Anti-Detection Features

- **Fingerprint Randomization** - Unique browser fingerprints per session
- **Timezone Spoofing** - Match proxy location
- **Locale Variation** - Random languages and regions
- **Canvas Noise** - Prevent canvas fingerprinting
- **WebGL Spoofing** - Randomized GPU/vendor strings
- **Plugin Simulation** - Realistic plugin lists
- **Font Emulation** - Varied font availability
- **Human Timing** - Natural delays and jitter
- **Mouse Movement** - Smooth, human-like cursor paths
- **Scroll Behavior** - Up/down scrolling with pauses

## 🐛 Troubleshooting

### Application Won't Start

- **License Error**: Verify license key with provider
- **Python Version**: Must be Python 3.11 or compatible
- **Missing Dependencies**: Run `pip install -r requirements.txt`
- **Playwright Not Installed**: Run `playwright install chromium`

### Proxy Issues

- **Connection Failed**: Verify proxy format and credentials
- **Timeout**: Check proxy is online and not blocked
- **Authentication Error**: Confirm username:password are correct

### Browser Issues

- **Browser Won't Launch**: Install Playwright browsers
- **Headless Errors**: Try disabling headless mode
- **CAPTCHA**: Use residential proxies, reduce speed

### Performance Issues

- **Slow Execution**: Reduce concurrent profiles
- **High CPU**: Lower thread count
- **Memory Usage**: Close other applications

## 📜 License

This software requires a valid license key for activation.

**License Types:**
- Personal License - Single device
- Business License - Multiple devices
- Enterprise License - Unlimited devices + support

Contact: [License Provider Website]

## ⚠️ Disclaimer

This tool is for educational and testing purposes only. Users are responsible for:
- Complying with website Terms of Service
- Respecting robots.txt and rate limits
- Following local laws and regulations
- Ethical use of automation tools

**DO NOT:**
- Violate website policies
- Perform DDoS attacks
- Scrape private/copyrighted data
- Circumvent security measures maliciously

## 🤝 Support

For issues, feature requests, or questions:
- **GitHub Issues**: https://github.com/RishiModiser/BOT/issues
- **Email**: [support email]
- **Documentation**: [wiki link]

## 📊 Version History

### v4.0 - JARVIS Edition (Current)
- ✅ Migrated to PyQt6
- ✅ JARVIS-style dark theme
- ✅ Visual RPA Script Builder
- ✅ Enhanced anti-detection
- ✅ Improved performance
- ✅ Better logging system
- ✅ Single-click .exe packaging

### v3.x - Previous Versions
- PyQt5 implementation
- Basic GUI
- Core automation features

## 🎨 Credits

**Developed by:** Copilot AI Assistant
**Original by:** RishiModiser
**UI Theme:** JARVIS-inspired design
**Framework:** PyQt6 + Playwright

---

**Made with ❤️ for Windows Desktop Automation**

*"The future of traffic simulation is here."* 🚀
