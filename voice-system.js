// Alfred's Voice Command System
class VoiceSystem {
    constructor(batcave) {
        this.batcave = batcave;
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.isListening = false;
        this.alfredVoice = null;
        this.init();
    }

    init() {
        this.setupSpeechRecognition();
        this.setupTextToSpeech();
        this.setupCommands();
        
        // Load saved voice preference after a delay
        setTimeout(() => {
            this.loadSavedVoicePreference();
        }, 2000);
    }

    setupSpeechRecognition() {
        // Check for browser support
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Speech Recognition not supported in this browser');
            return;
        }

        // Create recognition instance
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configure recognition settings
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';
        this.recognition.maxAlternatives = 1;

        // Event handlers
        this.recognition.onstart = () => {
            console.log('Voice recognition started');
            this.updateVoiceUI(true);
        };

        this.recognition.onresult = (event) => {
            const command = event.results[0][0].transcript.toLowerCase().trim();
            console.log('Voice command received:', command);
            this.processVoiceCommand(command);
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.handleVoiceError(event.error);
        };

        this.recognition.onend = () => {
            console.log('Voice recognition ended');
            this.updateVoiceUI(false);
        };
    }

    setupTextToSpeech() {
        // Wait for voices to load
        if (this.synthesis.getVoices().length === 0) {
            this.synthesis.addEventListener('voiceschanged', () => {
                this.selectAlfredVoice();
                this.populateVoiceSelector();
            });
        } else {
            this.selectAlfredVoice();
            this.populateVoiceSelector();
        }
    }

    populateVoiceSelector() {
        const selector = document.getElementById('voiceSelector');
        if (!selector) return;

        const voices = this.synthesis.getVoices();
        selector.innerHTML = '<option value="">Auto-Select Best Voice</option>';

        // Group voices by language/type for better organization
        const englishVoices = voices.filter(v => v.lang.includes('en'));
        const maleVoices = englishVoices.filter(v => 
            v.name.toLowerCase().includes('male') ||
            v.name.toLowerCase().includes('man') ||
            v.name.toLowerCase().includes('david') ||
            v.name.toLowerCase().includes('daniel') ||
            v.name.toLowerCase().includes('alex') ||
            v.name.toLowerCase().includes('sam') ||
            v.name.toLowerCase().includes('george')
        );
        const otherVoices = englishVoices.filter(v => !maleVoices.includes(v));

        // Add male voices first
        if (maleVoices.length > 0) {
            const maleGroup = document.createElement('optgroup');
            maleGroup.label = 'Male Voices (Recommended)';
            maleVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.voiceURI;
                option.textContent = `${voice.name} (${voice.lang})`;
                maleGroup.appendChild(option);
            });
            selector.appendChild(maleGroup);
        }

        // Add other English voices
        if (otherVoices.length > 0) {
            const otherGroup = document.createElement('optgroup');
            otherGroup.label = 'Other English Voices';
            otherVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.voiceURI;
                option.textContent = `${voice.name} (${voice.lang})`;
                otherGroup.appendChild(option);
            });
            selector.appendChild(otherGroup);
        }
    }

    setVoiceByURI(voiceURI) {
        if (!voiceURI) {
            // Auto-select
            this.selectAlfredVoice();
            return;
        }

        const voices = this.synthesis.getVoices();
        this.alfredVoice = voices.find(v => v.voiceURI === voiceURI);
        
        if (this.alfredVoice) {
            console.log('🎭 Manually selected voice:', this.alfredVoice.name);
            this.displayVoiceInfo();
            
            // Save preference
            localStorage.setItem('alfredVoiceURI', voiceURI);
        }
    }

    loadSavedVoicePreference() {
        const savedVoiceURI = localStorage.getItem('alfredVoiceURI');
        if (savedVoiceURI) {
            this.setVoiceByURI(savedVoiceURI);
            
            // Update selector
            const selector = document.getElementById('voiceSelector');
            if (selector) {
                selector.value = savedVoiceURI;
            }
        }
    }

    selectAlfredVoice() {
        const voices = this.synthesis.getVoices();
        
        // Debug: Show what we're working with
        console.log('🎤 Voice Selection Debug:');
        console.log('Total voices available:', voices.length);
        console.log('All voices:', voices.map(v => `"${v.name}" (${v.lang}) [${v.gender || 'unknown gender'}]`));
        
        // Mobile Chrome often has limited voices, so be more flexible
        const preferredVoices = [
            // High priority: Clearly British/Male
            'Google UK English Male',
            'Microsoft George',
            'Microsoft Daniel',
            'Daniel (Enhanced)',
            
            // Medium priority: Any male voice that sounds good
            'Google US English Male',
            'Microsoft David',
            'Alex',
            'Daniel',
            'Sam',
            'Fred',
            
            // Lower priority: Any voice with "male" in the name
            'Male',
            'Man'
        ];

        // Try exact matches first
        for (const preferred of preferredVoices) {
            this.alfredVoice = voices.find(voice => 
                voice.name === preferred || 
                voice.name.includes(preferred)
            );
            if (this.alfredVoice) {
                console.log('✅ Found exact match:', this.alfredVoice.name);
                break;
            }
        }

        // Try British/UK voices
        if (!this.alfredVoice) {
            this.alfredVoice = voices.find(voice => 
                voice.lang.includes('en-GB') || 
                voice.lang.includes('en-UK') ||
                voice.name.toLowerCase().includes('british') ||
                voice.name.toLowerCase().includes('uk')
            );
            if (this.alfredVoice) {
                console.log('✅ Found British voice:', this.alfredVoice.name);
            }
        }

        // Try any male-sounding voice
        if (!this.alfredVoice) {
            this.alfredVoice = voices.find(voice => 
                voice.name.toLowerCase().includes('male') || 
                voice.name.toLowerCase().includes('man') ||
                voice.name.toLowerCase().includes('david') ||
                voice.name.toLowerCase().includes('daniel') ||
                voice.name.toLowerCase().includes('alex') ||
                voice.name.toLowerCase().includes('sam') ||
                voice.name.toLowerCase().includes('fred')
            );
            if (this.alfredVoice) {
                console.log('✅ Found male-sounding voice:', this.alfredVoice.name);
            }
        }

        // Last resort: avoid obviously female voices
        if (!this.alfredVoice) {
            this.alfredVoice = voices.find(voice => 
                !voice.name.toLowerCase().includes('female') &&
                !voice.name.toLowerCase().includes('woman') &&
                !voice.name.toLowerCase().includes('girl') &&
                !voice.name.toLowerCase().includes('susan') &&
                !voice.name.toLowerCase().includes('mary') &&
                !voice.name.toLowerCase().includes('karen') &&
                !voice.name.toLowerCase().includes('sarah') &&
                voice.lang.includes('en')
            ) || voices.find(voice => voice.lang.includes('en')) || voices[0];
            
            if (this.alfredVoice) {
                console.log('⚠️ Using fallback voice:', this.alfredVoice.name);
            }
        }

        console.log('🎭 Final Alfred voice selection:', {
            name: this.alfredVoice?.name || 'Default',
            lang: this.alfredVoice?.lang || 'Unknown',
            voiceURI: this.alfredVoice?.voiceURI || 'Default'
        });
        
        // Create a voice info display for debugging
        this.displayVoiceInfo();
    }

    displayVoiceInfo() {
        // Add voice info to the interface for debugging
        const voiceResponse = document.getElementById('voiceResponse');
        if (voiceResponse && this.alfredVoice) {
            const infoDiv = document.createElement('div');
            infoDiv.style.cssText = `
                position: fixed; top: 10px; right: 10px; 
                background: rgba(0,0,0,0.8); color: #00d4ff; 
                padding: 10px; border-radius: 5px; font-size: 12px;
                z-index: 9999; max-width: 300px;
            `;
            infoDiv.innerHTML = `
                🎤 Voice: ${this.alfredVoice.name}<br>
                🌐 Lang: ${this.alfredVoice.lang}<br>
                🔊 URI: ${this.alfredVoice.voiceURI}
            `;
            infoDiv.id = 'voice-debug-info';
            
            // Remove existing debug info
            const existing = document.getElementById('voice-debug-info');
            if (existing) existing.remove();
            
            document.body.appendChild(infoDiv);
            
            // Auto-remove after 10 seconds
            setTimeout(() => infoDiv.remove(), 10000);
        }
    }

    setupCommands() {
        this.commands = {
            // Briefing commands
            'briefing': () => this.handleBriefingCommand(),
            'brief me': () => this.handleBriefingCommand(),
            'status report': () => this.handleBriefingCommand(),
            'what\'s the situation': () => this.handleBriefingCommand(),
            'update me': () => this.handleBriefingCommand(),

            // Weather commands  
            'weather': () => this.handleWeatherCommand(),
            'what\'s the weather': () => this.handleWeatherCommand(),
            'weather report': () => this.handleWeatherCommand(),
            'how\'s the weather': () => this.handleWeatherCommand(),

            // System commands
            'system status': () => this.handleSystemCommand(),
            'systems report': () => this.handleSystemCommand(),
            'how are the systems': () => this.handleSystemCommand(),
            'system check': () => this.handleSystemCommand(),

            // Financial commands
            'stocks': () => this.handleFinancialCommand(),
            'financial report': () => this.handleFinancialCommand(),
            'wayne enterprises': () => this.handleFinancialCommand(),
            'portfolio': () => this.handleFinancialCommand(),

            // Emergency commands
            'activate bat signal': () => this.handleEmergencyCommand(),
            'emergency': () => this.handleEmergencyCommand(),
            'bat signal': () => this.handleEmergencyCommand(),
            'alert': () => this.handleEmergencyCommand(),

            // Utility commands
            'time': () => this.handleTimeCommand(),
            'what time is it': () => this.handleTimeCommand(),
            'current time': () => this.handleTimeCommand(),

            // Personality commands
            'hello alfred': () => this.handleGreetingCommand(),
            'good evening alfred': () => this.handleGreetingCommand(),
            'how are you alfred': () => this.handleGreetingCommand(),
            'hello': () => this.handleGreetingCommand()
        };
    }

    startListening() {
        if (!this.recognition) {
            this.speak("I'm sorry, Master Bruce, but voice recognition is not available in this browser.");
            return;
        }

        if (this.isListening) {
            this.stopListening();
            return;
        }

        try {
            this.recognition.start();
            this.isListening = true;
        } catch (error) {
            console.error('Failed to start voice recognition:', error);
            this.speak("Voice recognition system encountered an error, sir.");
        }
    }

    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
        }
    }

    processVoiceCommand(command) {
        console.log('Processing command:', command);
        
        // Find matching command
        let matchedCommand = null;
        for (const [key, handler] of Object.entries(this.commands)) {
            if (command.includes(key) || this.similarity(command, key) > 0.7) {
                matchedCommand = handler;
                break;
            }
        }

        if (matchedCommand) {
            matchedCommand();
        } else {
            // Send unknown commands to Alfred AI
            this.handleUnknownCommand(command);
        }

        this.isListening = false;
    }

    // Command Handlers
    handleBriefingCommand() {
        this.batcave.generateBriefing();
        setTimeout(() => {
            const briefingText = document.getElementById('briefingText').textContent;
            this.speak(briefingText);
        }, 1000);
    }

    async handleWeatherCommand() {
        try {
            const response = await fetch('/api/weather');
            const weather = await response.json();
            
            // More detailed, butler-style weather report
            let weatherReport = `Master Bruce, the current conditions in ${weather.location || 'your area'} are as follows: `;
            weatherReport += `Temperature is ${weather.temperature} degrees Fahrenheit, `;
            weatherReport += `with ${weather.condition} skies. `;
            weatherReport += `Humidity stands at ${weather.humidity} percent, `;
            weatherReport += `and winds are ${weather.windSpeed} miles per hour. `;
            weatherReport += `Visibility is ${weather.visibility} miles. `;
            
            // Add threat assessment in butler style
            if (weather.threatLevel === "CLEAR") {
                weatherReport += `Conditions are quite suitable for any evening activities you might have planned, sir.`;
            } else {
                weatherReport += `I must advise caution, Master Bruce - ${weather.description}. `;
                weatherReport += `Perhaps consider adjusting your plans accordingly.`;
            }
            
            this.speak(weatherReport);
        } catch (error) {
            this.speak("I do apologize, Master Bruce, but I'm experiencing difficulties accessing current weather information. Shall I try again momentarily?");
        }
    }

    async handleSystemCommand() {
        const systems = document.querySelectorAll('.system-metric .metric-value');
        if (systems.length >= 3) {
            const power = systems[0].textContent;
            const security = systems[1].textContent; 
            const comms = systems[2].textContent;
            
            let systemReport = `Master Bruce, I'm pleased to report that all cave systems are performing admirably. `;
            systemReport += `Main power is operating at ${power} capacity, `;
            systemReport += `the security grid is functioning at ${security}, `;
            systemReport += `and our communications array is running at ${comms}. `;
            
            // Add assessment based on performance
            const avgPerformance = (parseInt(power) + parseInt(security) + parseInt(comms)) / 3;
            if (avgPerformance > 95) {
                systemReport += `Everything is running at peak efficiency, sir. Quite satisfactory.`;
            } else if (avgPerformance > 90) {
                systemReport += `All systems are well within acceptable parameters, Master Bruce.`;
            } else {
                systemReport += `I shall continue monitoring for any necessary maintenance, sir.`;
            }
            
            this.speak(systemReport);
        } else {
            this.speak("I do apologize, Master Bruce, but the system diagnostics are currently refreshing. Shall I try again in just a moment?");
        }
    }

    async handleFinancialCommand() {
        try {
            const response = await fetch('/api/stocks');
            const stocks = await response.json();
            const financialReport = `Wayne Enterprises portfolio value: ${stocks.portfolio.totalValue.toLocaleString()} dollars. Today's change: ${stocks.portfolio.dayChange >= 0 ? 'up' : 'down'} ${Math.abs(stocks.portfolio.dayChange).toLocaleString()} dollars. Market is currently ${stocks.portfolio.marketStatus.toLowerCase()}.`;
            this.speak(financialReport);
        } catch (error) {
            this.speak("Financial data is temporarily unavailable, sir.");
        }
    }

    handleEmergencyCommand() {
        this.batcave.activateBatSignal();
        this.speak("Bat-Signal activated, Master Bruce. Emergency protocols are now in effect. GCPD has been notified.");
    }

    handleTimeCommand() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
        this.speak(`The current time is ${timeString}, Master Bruce.`);
    }

    handleGreetingCommand() {
        const now = new Date();
        const hour = now.getHours();
        let timeGreeting = "";
        
        if (hour < 12) {
            timeGreeting = "Good morning";
        } else if (hour < 17) {
            timeGreeting = "Good afternoon";
        } else {
            timeGreeting = "Good evening";
        }
        
        const greetings = [
            `${timeGreeting}, Master Bruce. I trust you are well this evening. How may I be of service?`,
            `${timeGreeting}, sir. All systems are functioning perfectly and awaiting your instructions.`,
            `${timeGreeting}, Master Bruce. The command center is fully operational and at your disposal.`,
            `Welcome back, sir. I have been monitoring all systems in your absence. Everything is quite in order.`,
            `${timeGreeting}, Master Bruce. Shall I provide you with a status update, or is there something specific you require?`,
            `At your service as always, sir. The evening's operations are proceeding smoothly.`
        ];
        
        const greeting = greetings[Math.floor(Math.random() * greetings.length)];
        this.speak(greeting);
    }

    async handleUnknownCommand(command) {
        // Send to Alfred AI for processing
        try {
            const response = await this.sendToAlfredAI(command);
            this.speak(response);
        } catch (error) {
            const fallbackResponses = [
                "I'm not certain what you're asking, Master Bruce. Could you rephrase that?",
                "I don't quite understand that command, sir. Perhaps try a different approach?",
                "My apologies, Master Bruce, but I didn't catch that. Could you repeat the command?",
                "That command is not in my current protocols, sir. What else can I help you with?"
            ];
            
            const fallback = fallbackResponses[Math.floor(Math.random() * fallbackResponses.length)];
            this.speak(fallback);
        }
    }

    async sendToAlfredAI(message) {
        try {
            // This would connect to OpenClaw/Alfred AI - for now, simulate
            const aiResponses = [
                "I'm processing that request, Master Bruce. Stand by.",
                "Interesting question, sir. Let me analyze the situation.",
                "I understand your concern, Master Bruce. Everything appears to be in order.",
                "That's a thoughtful inquiry, sir. I'll monitor the situation.",
                "Noted, Master Bruce. I'll keep that in mind for future operations."
            ];
            
            return aiResponses[Math.floor(Math.random() * aiResponses.length)];
        } catch (error) {
            throw new Error('AI communication failed');
        }
    }

    speak(text) {
        // Stop any current speech
        this.synthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Configure voice settings for British Butler Alfred
        if (this.alfredVoice) {
            utterance.voice = this.alfredVoice;
        }
        
        // British Butler voice characteristics
        utterance.rate = 0.85;  // Measured, dignified pace
        utterance.pitch = 0.75; // Lower pitch for authority and age
        utterance.volume = 0.9; // Clear and commanding
        
        // Add more sophisticated pauses and emphasis for butler speech
        let enhancedText = text
            .replace(/\bMaster Bruce\b/g, 'Master Bruce,') // Pause after addressing
            .replace(/\bsir\b/g, 'sir,') // Respectful pause
            .replace(/\./g, '... ') // Longer pauses at sentences
            .replace(/,/g, ', ') // Brief pauses at commas
            .replace(/:/g, ': ') // Pause after colons
            .replace(/;/g, '; '); // Pause after semicolons

        // Add British butler formality to responses
        if (!text.toLowerCase().includes('master bruce') && !text.toLowerCase().includes('sir')) {
            if (Math.random() < 0.3) {
                enhancedText = 'Sir, ' + enhancedText;
            }
        }

        utterance.text = enhancedText;

        // Visual feedback
        this.updateSpeechUI(true);
        
        utterance.onend = () => {
            this.updateSpeechUI(false);
        };

        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event);
            this.updateSpeechUI(false);
        };

        this.synthesis.speak(utterance);
        
        // Debugging: log the actual voice being used
        console.log('Speaking with voice:', utterance.voice?.name || 'Default');
    }

    updateVoiceUI(listening) {
        const voiceBtn = document.getElementById('voiceBtn');
        const voiceResponse = document.getElementById('voiceResponse');
        
        if (listening) {
            voiceBtn.classList.add('active');
            voiceBtn.innerHTML = '<i class="fas fa-microphone-slash"></i><span>LISTENING...</span>';
            voiceResponse.textContent = 'Listening for voice command, Master Bruce...';
        } else {
            voiceBtn.classList.remove('active');
            voiceBtn.innerHTML = '<i class="fas fa-microphone"></i><span>VOICE COMMAND</span>';
            if (!this.synthesis.speaking) {
                setTimeout(() => {
                    voiceResponse.textContent = '';
                }, 2000);
            }
        }
    }

    updateSpeechUI(speaking) {
        const voiceResponse = document.getElementById('voiceResponse');
        
        if (speaking) {
            voiceResponse.textContent = 'Alfred is responding...';
            voiceResponse.style.color = '#00d4ff';
            voiceResponse.style.fontStyle = 'italic';
        } else {
            setTimeout(() => {
                voiceResponse.textContent = '';
                voiceResponse.style.color = '';
                voiceResponse.style.fontStyle = '';
            }, 1000);
        }
    }

    handleVoiceError(error) {
        console.error('Voice recognition error:', error);
        
        const errorMessages = {
            'network': "Network error, Master Bruce. Check your connection.",
            'not-allowed': "Voice access denied. Please allow microphone permissions.",
            'no-speech': "I didn't detect any speech, sir. Please try again.", 
            'aborted': "Voice recognition was interrupted.",
            'audio-capture': "Microphone not available. Please check your audio settings."
        };

        const message = errorMessages[error] || "Voice system encountered an error, sir.";
        this.speak(message);
        
        this.updateVoiceUI(false);
    }

    // Utility function for fuzzy matching
    similarity(s1, s2) {
        const longer = s1.length > s2.length ? s1 : s2;
        const shorter = s1.length > s2.length ? s2 : s1;
        
        if (longer.length === 0) return 1.0;
        
        const editDistance = this.levenshteinDistance(longer, shorter);
        return (longer.length - editDistance) / longer.length;
    }

    levenshteinDistance(s1, s2) {
        const matrix = [];
        
        for (let i = 0; i <= s2.length; i++) {
            matrix[i] = [i];
        }
        
        for (let j = 0; j <= s1.length; j++) {
            matrix[0][j] = j;
        }
        
        for (let i = 1; i <= s2.length; i++) {
            for (let j = 1; j <= s1.length; j++) {
                if (s2.charAt(i - 1) === s1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        
        return matrix[s2.length][s1.length];
    }
}

// Export for use in main batcave.js
window.VoiceSystem = VoiceSystem;

// Global functions for HTML onclick handlers
window.toggleVoiceSettings = function() {
    const settings = document.getElementById('voiceSettings');
    const btn = document.getElementById('voiceSettingsBtn');
    
    if (settings.style.display === 'none') {
        settings.style.display = 'block';
        btn.style.color = '#00d4ff';
        btn.style.borderColor = '#00d4ff';
        btn.style.background = 'rgba(0, 212, 255, 0.1)';
    } else {
        settings.style.display = 'none';
        btn.style.color = '';
        btn.style.borderColor = '';
        btn.style.background = '';
    }
};

window.changeAlfredVoice = function() {
    const selector = document.getElementById('voiceSelector');
    const voiceSystem = window.batcave?.voiceSystem;
    
    if (selector && voiceSystem) {
        voiceSystem.setVoiceByURI(selector.value);
    }
};

window.testCurrentVoice = function() {
    const voiceSystem = window.batcave?.voiceSystem;
    
    if (voiceSystem) {
        const testPhrases = [
            "Good evening, Master Bruce. Voice test successful.",
            "All systems operational, sir. How do I sound?",
            "Testing voice parameters, Master Bruce. Is this more to your liking?"
        ];
        
        const phrase = testPhrases[Math.floor(Math.random() * testPhrases.length)];
        voiceSystem.speak(phrase);
    }
};