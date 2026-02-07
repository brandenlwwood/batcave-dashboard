// Alfred's Batcave Command Center - JavaScript
class BatcaveSystem {
    constructor() {
        this.isVoiceActive = false;
        this.voiceSystem = null;
        this.briefings = [
            "Good evening, Master Bruce. All systems operational. No significant threats detected in Gotham.",
            "Sir, GCPD reports quiet night. Wayne Enterprises stock performing well. Recommend routine patrol.",
            "Master Bruce, weather conditions optimal for surveillance. All cave systems functioning normally.",
            "Evening briefing: Gotham secure, finances stable, equipment ready. The city sleeps safely tonight.",
            "Sir, monitoring social channels shows no unusual criminal activity. Consider this a peaceful evening.",
            "All quiet on the western front, Master Bruce. Perfect time for strategic planning or equipment upgrades."
        ];
        this.init();
    }

    init() {
        this.updateTime();
        this.setupEventListeners();
        this.initializeModules();
        this.initializeVoiceSystem();
        this.startPeriodicUpdates();
        this.generateBriefing();
        this.playSystemSound();
        
        // Add fade-in animation to modules
        setTimeout(() => {
            document.querySelectorAll('.cave-module').forEach((module, index) => {
                setTimeout(() => {
                    module.classList.add('fade-in');
                }, index * 100);
            });
        }, 500);
    }

    setupEventListeners() {
        // Bat logo click effect
        document.getElementById('batLogo').addEventListener('click', () => {
            this.activateSystemEffect();
        });

        // Voice control
        document.getElementById('voiceBtn').addEventListener('click', () => {
            this.toggleVoiceControl();
        });

        // Module hover effects
        document.querySelectorAll('.cave-module').forEach(module => {
            module.addEventListener('mouseenter', () => {
                this.playSystemSound('hover');
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'b') {
                e.preventDefault();
                this.generateBriefing();
            }
            if (e.ctrlKey && e.key === 'v') {
                e.preventDefault();
                this.toggleVoiceControl();
            }
        });
    }

    initializeModules() {
        this.updateWeather();
        this.updateSurveillance();
        this.updateFinancials();
        this.updateCommunications();
        this.updateSchedule();
        this.updateDiagnostics();
    }

    initializeVoiceSystem() {
        // Initialize voice system after page load
        setTimeout(() => {
            if (window.VoiceSystem) {
                this.voiceSystem = new VoiceSystem(this);
                console.log('Voice system initialized');
                
                // Add voice capability indicator
                const voiceBtn = document.getElementById('voiceBtn');
                if (voiceBtn && this.voiceSystem.recognition) {
                    voiceBtn.title = 'Real voice commands enabled! Try saying: "Hello Alfred" or "Weather report"';
                    voiceBtn.style.borderColor = '#00ff88';
                } else {
                    voiceBtn.title = 'Voice commands not supported in this browser';
                    voiceBtn.style.borderColor = '#ffab00';
                }
            }
        }, 1000);
    }

    startPeriodicUpdates() {
        // Update time every second
        setInterval(() => this.updateTime(), 1000);
        
        // Update modules every 30 seconds
        setInterval(() => {
            this.updateSurveillance();
            this.updateDiagnostics();
        }, 30000);
        
        // Update weather every 10 minutes
        setInterval(() => this.updateWeather(), 600000);
        
        // Update financials every 5 minutes (during market hours)
        setInterval(() => this.updateFinancials(), 300000);
        
        // Generate new briefing every 15 minutes
        setInterval(() => this.generateBriefing(), 900000);
    }

    updateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        document.getElementById('currentTime').textContent = timeString;
    }

    async updateWeather() {
        try {
            // Simulated weather data - in real implementation, use actual weather API
            const weatherData = {
                temperature: Math.floor(Math.random() * 30) + 40,
                humidity: Math.floor(Math.random() * 40) + 40,
                windSpeed: Math.floor(Math.random() * 15) + 5,
                visibility: Math.floor(Math.random() * 5) + 8,
                condition: 'clear'
            };

            document.getElementById('temperature').textContent = `${weatherData.temperature}°F`;
            document.getElementById('humidity').textContent = `${weatherData.humidity}%`;
            document.getElementById('windSpeed').textContent = `${weatherData.windSpeed} mph`;
            document.getElementById('visibility').textContent = `${weatherData.visibility} mi`;

            // Update threat level based on conditions
            let threatLevel = 'CLEAR';
            let threatClass = 'threat-level';
            
            if (weatherData.visibility < 5 || weatherData.windSpeed > 20) {
                threatLevel = 'CAUTION';
                threatClass += ' warning';
            }
            
            document.getElementById('weatherThreat').textContent = threatLevel;
            document.getElementById('weatherThreat').className = threatClass;

        } catch (error) {
            console.error('Weather update failed:', error);
        }
    }

    updateSurveillance() {
        const activities = [
            "Perimeter scan complete - no anomalies detected",
            "Traffic monitoring systems operational",
            "GCPD communications intercepted - routine patrol",
            "Social media sentiment analysis: Gotham morale stable",
            "Facial recognition scan: No known criminals detected",
            "Network security sweep completed successfully",
            "Drone surveillance - East End sector clear",
            "Oracle systems synchronized and operational"
        ];

        const randomActivity = activities[Math.floor(Math.random() * activities.length)];
        const now = new Date();
        const timestamp = now.toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        document.getElementById('lastActivity').textContent = timestamp;
        document.getElementById('activityText').textContent = randomActivity;

        // Update alert count (usually 0 for a peaceful night)
        const alertCount = Math.random() < 0.1 ? Math.floor(Math.random() * 3) + 1 : 0;
        document.getElementById('alertCount').textContent = alertCount;

        // Update news ticker
        const newsItems = [
            "WAYNE ENTERPRISES ANNOUNCES NEW SECURITY INITIATIVE",
            "GCPD REPORTS CRIME DOWN 15% THIS QUARTER",
            "GOTHAM UNIVERSITY BREAKTHROUGH IN CLEAN ENERGY",
            "MAYOR'S OFFICE PRAISES RECENT INFRASTRUCTURE IMPROVEMENTS",
            "WAYNE FOUNDATION DONATES $2M TO CHILDREN'S HOSPITAL",
            "ARKHAM ASYLUM REPORTS ALL INMATES ACCOUNTED FOR"
        ];
        
        const ticker = document.getElementById('tickerContent');
        if (ticker) {
            const randomNews = newsItems[Math.floor(Math.random() * newsItems.length)];
            ticker.textContent = `${randomNews} • SYSTEM STATUS: OPTIMAL • ALL SECTORS SECURE • STANDING BY FOR ORDERS`;
        }
    }

    updateFinancials() {
        // Simulated stock data
        const stocks = [
            { symbol: 'WE', basePrice: 147.52 },
            { symbol: 'TECH', basePrice: 89.21 },
            { symbol: 'ENERGY', basePrice: 134.67 },
            { symbol: 'DEFENSE', basePrice: 98.43 }
        ];

        const stockTicker = document.getElementById('stockTicker');
        if (stockTicker) {
            stockTicker.innerHTML = '';
            
            stocks.slice(0, 2).forEach(stock => {
                const change = (Math.random() - 0.5) * 10; // -5% to +5%
                const newPrice = stock.basePrice + change;
                const changePercent = (change / stock.basePrice * 100).toFixed(2);
                
                const stockItem = document.createElement('div');
                stockItem.className = 'stock-item';
                stockItem.innerHTML = `
                    <span class="symbol">${stock.symbol}</span>
                    <span class="price">$${newPrice.toFixed(2)}</span>
                    <span class="change ${change >= 0 ? 'positive' : 'negative'}">
                        ${change >= 0 ? '+' : ''}${changePercent}%
                    </span>
                `;
                stockTicker.appendChild(stockItem);
            });
        }

        // Update portfolio value
        const portfolioBase = 2847392;
        const portfolioChange = (Math.random() - 0.5) * 100000;
        const newValue = portfolioBase + portfolioChange;
        
        const valueElements = document.querySelectorAll('.portfolio-summary .value');
        if (valueElements.length >= 2) {
            valueElements[0].textContent = `$${newValue.toLocaleString()}`;
            valueElements[1].textContent = `${portfolioChange >= 0 ? '+' : ''}$${Math.abs(portfolioChange).toLocaleString()}`;
            valueElements[1].className = `value ${portfolioChange >= 0 ? 'positive' : 'negative'}`;
        }

        // Update market status
        const now = new Date();
        const hour = now.getHours();
        const isMarketOpen = hour >= 9 && hour < 16; // Simplified market hours
        document.getElementById('marketStatus').textContent = isMarketOpen ? 'OPEN' : 'CLOSED';
    }

    updateCommunications() {
        const messages = [
            { sender: 'GCPD', preview: 'All patrol units reporting normal activity', urgent: false },
            { sender: 'ORACLE', preview: 'Database synchronization complete', urgent: false },
            { sender: 'LUCIUS FOX', preview: 'New equipment ready for field testing', urgent: false },
            { sender: 'WAYNE ENTERPRISES', preview: 'Board meeting scheduled for tomorrow', urgent: false },
            { sender: 'COMMISSIONER GORDON', preview: 'Requesting consultation on cold case', urgent: true },
            { sender: 'SECURITY TEAM', preview: 'Manor perimeter secure, all systems green', urgent: false }
        ];

        const messageQueue = document.getElementById('messageQueue');
        if (messageQueue) {
            messageQueue.innerHTML = '';
            
            // Select 2-3 random messages
            const selectedMessages = messages
                .sort(() => 0.5 - Math.random())
                .slice(0, Math.floor(Math.random() * 2) + 2);

            selectedMessages.forEach(msg => {
                const messageItem = document.createElement('div');
                messageItem.className = `message-item ${msg.urgent ? 'urgent' : ''}`;
                
                const now = new Date();
                const timestamp = now.toLocaleTimeString('en-US', { 
                    hour12: false, 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                
                messageItem.innerHTML = `
                    <div class="sender">${msg.sender}</div>
                    <div class="preview">${msg.preview}</div>
                    <div class="timestamp">${timestamp}</div>
                `;
                messageQueue.appendChild(messageItem);
            });
        }
    }

    updateSchedule() {
        const now = new Date();
        const scheduleItems = [
            {
                time: this.addMinutes(now, 60).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
                event: 'Perimeter Sweep - East End',
                status: 'pending'
            },
            {
                time: this.addMinutes(now, 150).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
                event: 'Wayne Enterprises Security Review',
                status: 'scheduled'
            },
            {
                time: this.addMinutes(now, 75).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
                event: 'Equipment Maintenance Check',
                status: 'routine'
            }
        ];

        const scheduleDisplay = document.getElementById('scheduleDisplay');
        if (scheduleDisplay) {
            scheduleDisplay.innerHTML = '';
            
            scheduleItems.forEach(item => {
                const scheduleItem = document.createElement('div');
                scheduleItem.className = 'schedule-item';
                scheduleItem.innerHTML = `
                    <div class="time">${item.time}</div>
                    <div class="event">${item.event}</div>
                    <div class="status ${item.status}">${item.status.toUpperCase()}</div>
                `;
                scheduleDisplay.appendChild(scheduleItem);
            });
        }

        // Update priority indicator
        const priorityLevel = Math.random() < 0.3 ? 'MEDIUM' : 'LOW';
        document.getElementById('priorityIndicator').textContent = priorityLevel;
    }

    updateDiagnostics() {
        // Simulate system metrics with slight variations
        const metrics = [
            { name: 'Main Power', value: Math.floor(Math.random() * 5) + 95 },
            { name: 'Security Grid', value: Math.floor(Math.random() * 3) + 97 },
            { name: 'Comms Array', value: Math.floor(Math.random() * 8) + 92 }
        ];

        const diagnosticsDisplay = document.querySelector('.diagnostics-display');
        if (diagnosticsDisplay) {
            diagnosticsDisplay.innerHTML = '';
            
            metrics.forEach(metric => {
                const metricDiv = document.createElement('div');
                metricDiv.className = 'system-metric';
                metricDiv.innerHTML = `
                    <span>${metric.name}</span>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${metric.value}%"></div>
                    </div>
                    <span class="metric-value">${metric.value}%</span>
                `;
                diagnosticsDisplay.appendChild(metricDiv);
            });
        }

        // Update overall system health
        const avgHealth = metrics.reduce((sum, m) => sum + m.value, 0) / metrics.length;
        let healthStatus = 'OPTIMAL';
        if (avgHealth < 95) healthStatus = 'GOOD';
        if (avgHealth < 90) healthStatus = 'CAUTION';
        
        document.getElementById('systemHealth').textContent = healthStatus;
    }

    generateBriefing() {
        const briefingText = document.getElementById('briefingText');
        const randomBriefing = this.briefings[Math.floor(Math.random() * this.briefings.length)];
        
        // Add current status information
        const now = new Date();
        const timeContext = now.getHours() < 12 ? 'morning' : 
                           now.getHours() < 18 ? 'afternoon' : 'evening';
        
        const enhancedBriefing = `${randomBriefing} Current time: ${timeContext}. All systems reporting normal parameters. Standing by for further instructions, sir.`;
        
        // Typewriter effect
        briefingText.textContent = '';
        briefingText.classList.remove('typing');
        
        setTimeout(() => {
            briefingText.classList.add('typing');
            this.typeText(briefingText, enhancedBriefing, 50);
        }, 100);
        
        this.playSystemSound('briefing');
    }

    typeText(element, text, speed = 50) {
        element.textContent = '';
        let i = 0;
        
        const typeInterval = setInterval(() => {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
            } else {
                clearInterval(typeInterval);
                // Remove typing cursor after completion
                setTimeout(() => {
                    element.classList.remove('typing');
                }, 1000);
            }
        }, speed);
    }

    toggleVoiceControl() {
        if (this.voiceSystem) {
            // Use real voice system
            this.voiceSystem.startListening();
        } else {
            // Fallback to simulated system
            const voiceBtn = document.getElementById('voiceBtn');
            const voiceResponse = document.getElementById('voiceResponse');
            
            this.isVoiceActive = !this.isVoiceActive;
            
            if (this.isVoiceActive) {
                voiceBtn.classList.add('active');
                voiceBtn.innerHTML = '<i class="fas fa-microphone-slash"></i><span>LISTENING...</span>';
                voiceResponse.textContent = 'Voice system not available - simulated response...';
                
                // Simulate voice recognition
                setTimeout(() => {
                    this.processVoiceCommand();
                }, 3000);
                
            } else {
                voiceBtn.classList.remove('active');
                voiceBtn.innerHTML = '<i class="fas fa-microphone"></i><span>VOICE COMMAND</span>';
                voiceResponse.textContent = '';
            }
        }
    }

    processVoiceCommand() {
        const responses = [
            "Command acknowledged, sir. Executing routine system scan.",
            "Yes, Master Bruce. All systems are functioning within normal parameters.",
            "Understood, sir. Initiating security protocol update.",
            "Very good, sir. I'll monitor the situation and report any changes.",
            "Of course, Master Bruce. The cave systems are at your disposal.",
            "Right away, sir. Scanning for any unusual activity in the area."
        ];
        
        const voiceBtn = document.getElementById('voiceBtn');
        const voiceResponse = document.getElementById('voiceResponse');
        
        const randomResponse = responses[Math.floor(Math.random() * responses.length)];
        
        voiceResponse.textContent = randomResponse;
        this.isVoiceActive = false;
        voiceBtn.classList.remove('active');
        voiceBtn.innerHTML = '<i class="fas fa-microphone"></i><span>VOICE COMMAND</span>';
        
        this.playSystemSound('response');
        
        // Clear response after 5 seconds
        setTimeout(() => {
            voiceResponse.textContent = '';
        }, 5000);
    }

    activateBatSignal() {
        const batSignal = document.getElementById('batSignal');
        const originalContent = batSignal.innerHTML;
        
        batSignal.style.background = 'rgba(255, 51, 51, 0.2)';
        batSignal.style.borderColor = '#ff3333';
        batSignal.innerHTML = '<i class="fas fa-exclamation-triangle"></i><span>SIGNAL ACTIVATED</span>';
        
        // Flash effect
        let flashCount = 0;
        const flashInterval = setInterval(() => {
            batSignal.style.opacity = batSignal.style.opacity === '0.3' ? '1' : '0.3';
            flashCount++;
            
            if (flashCount >= 6) {
                clearInterval(flashInterval);
                batSignal.style.opacity = '1';
                batSignal.style.background = '';
                batSignal.style.borderColor = '';
                batSignal.innerHTML = originalContent;
            }
        }, 200);
        
        this.playSystemSound('alert');
        
        // Show emergency message
        setTimeout(() => {
            document.getElementById('voiceResponse').textContent = 
                'Emergency signal transmitted, Master Bruce. GCPD has been notified.';
        }, 1000);
        
        setTimeout(() => {
            document.getElementById('voiceResponse').textContent = '';
        }, 5000);
    }

    activateSystemEffect() {
        // Add glitch effect to random modules
        const modules = document.querySelectorAll('.cave-module');
        const randomModule = modules[Math.floor(Math.random() * modules.length)];
        
        randomModule.classList.add('glitch');
        setTimeout(() => {
            randomModule.classList.remove('glitch');
        }, 300);
        
        // Pulse bat logo
        const batLogo = document.getElementById('batLogo');
        batLogo.style.transform = 'scale(1.2)';
        batLogo.style.color = '#ff3333';
        
        setTimeout(() => {
            batLogo.style.transform = '';
            batLogo.style.color = '';
        }, 300);
        
        this.playSystemSound('system');
    }

    playSystemSound(type = 'default') {
        // Create audio context for system sounds
        if (window.AudioContext || window.webkitAudioContext) {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Different tones for different actions
            const frequencies = {
                'default': 440,
                'hover': 220,
                'briefing': 330,
                'response': 550,
                'alert': 880,
                'system': 660
            };
            
            const frequency = frequencies[type] || frequencies['default'];
            
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.setValueAtTime(frequency, audioContext.currentTime);
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0, audioContext.currentTime);
            gainNode.gain.linearRampToValueAtTime(0.1, audioContext.currentTime + 0.01);
            gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.1);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.1);
        }
    }

    addMinutes(date, minutes) {
        return new Date(date.getTime() + minutes * 60000);
    }
}

// Global functions for HTML onclick handlers
function generateBriefing() {
    batcave.generateBriefing();
}

function activateBatSignal() {
    batcave.activateBatSignal();
}

function toggleVoiceControl() {
    batcave.toggleVoiceControl();
}

// Initialize the Batcave system when page loads
let batcave;
document.addEventListener('DOMContentLoaded', () => {
    batcave = new BatcaveSystem();
    
    console.log(`
    ██████╗  █████╗ ████████╗ ██████╗ █████╗ ██╗   ██╗███████╗
    ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔══██╗██║   ██║██╔════╝
    ██████╔╝███████║   ██║   ██║     ███████║██║   ██║█████╗  
    ██╔══██╗██╔══██║   ██║   ██║     ██╔══██║╚██╗ ██╔╝██╔══╝  
    ██████╔╝██║  ██║   ██║   ╚██████╗██║  ██║ ╚████╔╝ ███████╗
    ╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝
    
    Alfred's Command Center - Systems Online
    `);
});