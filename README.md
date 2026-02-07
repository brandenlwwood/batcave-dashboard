# 🦇 Alfred's Batcave Command Center

*A cinematic, Batman-themed dashboard with real voice commands and live data monitoring.*

![Batcave Dashboard Preview](https://img.shields.io/badge/Status-Live-green) ![Voice Commands](https://img.shields.io/badge/Voice-Enabled-blue) ![Mobile Ready](https://img.shields.io/badge/Mobile-Responsive-purple)

## ✨ Features

### 🎭 **Cinematic Experience**
- **Dark Batman Theme** with animated effects and pulsing bat logo
- **Authentic Sound Effects** for interactions and system events  
- **Typing Animations** for mission briefings and status updates
- **Visual Glitch Effects** and dramatic lighting

### 🗣️ **Real Voice Commands**
- **Web Speech API Integration** - Actually talk to Alfred!
- **British Butler Voice** - Alfred responds with proper TTS
- **Smart Command Recognition** with fuzzy matching
- **15+ Voice Commands** including weather, stocks, system status

### 📊 **Live Data Modules**
- **🌤️ Real Weather** - Live data for any location with threat assessment
- **💼 Stock Tracking** - Wayne Enterprises portfolio monitoring
- **👁️ Surveillance** - Activity monitoring and news ticker
- **📡 Communications** - Message queue from various sources
- **⚙️ System Diagnostics** - Cave systems health monitoring
- **📅 Mission Schedule** - Upcoming events and patrol times

### 📱 **Technical Excellence**
- **Mobile Responsive** - Perfect on phones, tablets, desktops
- **HTTPS Support** - Enables microphone access for voice commands
- **Manual Voice Selection** - Choose from available TTS voices
- **Settings Persistence** - Remembers your preferences
- **Real APIs** - Weather data from wttr.in and weather.gov

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- Modern web browser with microphone support
- HTTPS connection for voice features

### Installation

```bash
# Clone the repository
git clone https://github.com/brandenlwwood/batcave-dashboard.git
cd batcave-dashboard

# Start the HTTPS server (recommended for voice commands)
./start-batcave.sh
# or specify port: ./start-batcave.sh 8080

# For HTTPS with voice support:
python3 https-server.py 8443
```

### Access URLs
- **HTTP:** http://localhost:8080
- **HTTPS:** https://localhost:8443 (for voice commands)
- **Network:** Replace localhost with your IP for remote access

## 🎮 Usage

### 🗣️ **Voice Commands**
Enable microphone access when prompted, then try:

| Command | Alfred's Response |
|---------|-------------------|
| "Hello Alfred" | Greeting with current time context |
| "Weather report" | Detailed weather briefing |  
| "System status" | Cave systems diagnostic |
| "Briefing" | Mission status update |
| "Stocks" | Financial portfolio report |
| "What time is it" | Current time |
| "Activate bat signal" | Emergency protocol! |

### 🖱️ **Interactive Elements**
- **Click Bat Logo** → System glitch effects
- **Click Voice Settings** → Choose different TTS voices  
- **Click Bat-Signal** → Emergency alert activation
- **Click Refresh Briefing** → New mission update

### ⌨️ **Keyboard Shortcuts**
- `Ctrl + B` → Generate new briefing
- `Ctrl + V` → Toggle voice control

## 🛠️ **Customization**

### 🌍 **Weather Location**
Edit `server.py` to change the weather location:

```python
# In get_real_weather_data() function
url = "https://wttr.in/YourCity,State?format=j1"
```

### 🎨 **Theme Colors**
Modify `batcave.css` variables:

```css
:root {
    --bat-primary: #0a0a0a;      /* Background */
    --bat-accent: #00d4ff;       /* Accent color */
    --bat-success: #00ff88;      /* Success color */
}
```

### 🗣️ **Voice Personality**
Customize Alfred's responses in `voice-system.js`:

```javascript
const greetings = [
    "Your custom greeting here, Master Bruce",
    "Another personalized response"
];
```

## 🏗️ **Architecture**

### Backend (`server.py`)
- **Python HTTP Server** serving static files and APIs
- **Real Weather Integration** with wttr.in and weather.gov
- **Simulated Data** for stocks, surveillance, communications
- **RESTful API Endpoints** for all dashboard modules

### Frontend
- **`index.html`** - Main dashboard structure
- **`batcave.css`** - Batman-themed styling with animations  
- **`batcave.js`** - Core dashboard functionality and data updates
- **`voice-system.js`** - Speech recognition and TTS integration

### Voice System
- **Web Speech API** for voice recognition
- **Speech Synthesis** for Alfred's responses
- **Smart Voice Selection** with British accent preference
- **Command Processing** with fuzzy matching

## 📱 **Mobile Support**

The dashboard is fully responsive and works great on mobile:
- **Touch-friendly** interface with proper button sizing
- **Mobile-optimized** layouts and fonts
- **Voice commands** work on mobile browsers with microphone
- **Swipe gestures** for module interactions

## 🔒 **Security Notes**

- **HTTPS Required** for microphone access on most browsers
- **Self-signed certificates** included for local development
- **No external data storage** - all data stays local
- **API rate limiting** built into weather services

## 🎬 **Demo Tips**

Perfect for showing off:
1. **Dark theme** immediately impresses visually
2. **Voice commands** - "Hello Alfred" gets great reactions
3. **Live weather** shows real functionality 
4. **Mobile responsive** - works perfectly on phones
5. **Interactive effects** - clicking bat logo creates glitch effects

## 🐛 **Troubleshooting**

### Voice Commands Not Working
1. **Check HTTPS** - Use https://localhost:8443 not http://
2. **Allow microphone** when browser prompts
3. **Try voice settings** - Click gear icon to select different voice
4. **Check console** - Look for voice debug messages

### Weather Data Issues  
- **Fallback included** - System shows simulated data if APIs fail
- **Multiple providers** - wttr.in with weather.gov backup
- **Timeout handling** - Graceful degradation after 10 seconds

### Mobile Issues
- **Use HTTPS** for full functionality
- **Enable location** if using location-based features
- **Clear cache** if styles not loading

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with proper commit messages
4. Test on both desktop and mobile
5. Submit a pull request

## 📄 **License**

This project is open source and available under the [MIT License](LICENSE).

## 👨‍💻 **Author**

**Branden Wood**
- GitHub: [@brandenlwwood](https://github.com/brandenlwwood)
- Project: Alfred's Batcave Command Center

---

*"Because every Batman needs a proper command center, Master Bruce." - Alfred* 🎩