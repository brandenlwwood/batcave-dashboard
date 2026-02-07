#!/usr/bin/env python3
"""
Alfred's Batcave Command Center Server
Serves the dashboard and provides API endpoints for real data
"""

import os
import json
import sys
import random
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

class BatcaveHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path.startswith('/api/'):
            self.handle_api_request(parsed_path)
        else:
            # Serve static files
            super().do_GET()
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def handle_api_request(self, parsed_path):
        """Handle API endpoints"""
        try:
            if parsed_path.path == '/api/weather':
                self.serve_weather_data()
            elif parsed_path.path == '/api/stocks':
                self.serve_stock_data()
            elif parsed_path.path == '/api/news':
                self.serve_news_data()
            elif parsed_path.path == '/api/schedule':
                self.serve_schedule_data()
            elif parsed_path.path == '/api/briefing':
                self.serve_briefing_data()
            else:
                self.send_error(404, "API endpoint not found")
        except Exception as e:
            self.send_json_error(500, str(e))
    
    def serve_weather_data(self):
        """Serve real weather data for Dumfries, VA"""
        try:
            # Get real weather data for Dumfries, VA
            weather = self.get_real_weather_data()
            self.send_json_response(weather)
        except Exception as e:
            print(f"Weather API error: {e}")
            # Fallback to simulated data
            weather = {
                "temperature": random.randint(40, 75),
                "humidity": random.randint(40, 80),
                "windSpeed": random.randint(5, 20),
                "visibility": random.randint(5, 15),
                "condition": "unknown",
                "threatLevel": "CLEAR",
                "description": "Weather data temporarily unavailable",
                "location": "Dumfries, VA (simulated)"
            }
            
            # Determine threat level
            if weather["visibility"] < 8 or weather["windSpeed"] > 15:
                weather["threatLevel"] = "CAUTION"
                weather["description"] = "Reduced visibility - exercise caution"
            
            self.send_json_response(weather)

    def get_real_weather_data(self):
        """Get real weather data for Dumfries, VA using OpenWeather-compatible free service"""
        import urllib.request
        import urllib.error
        
        # Using wttr.in - free weather service, no API key needed
        try:
            # Dumfries, VA coordinates: 38.5768, -77.3202
            url = "https://wttr.in/Dumfries,VA?format=j1"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            current = data['current_condition'][0]
            
            # Convert to our format
            temp_f = int(current['temp_F'])
            humidity = int(current['humidity'])
            wind_mph = int(float(current['windspeedMiles']))
            visibility_mi = int(float(current['visibility']))
            condition = current['weatherDesc'][0]['value'].lower()
            
            # Determine threat level based on conditions
            threat_level = "CLEAR"
            description = "Optimal conditions for operations"
            
            if visibility_mi < 5:
                threat_level = "CAUTION"
                description = "Reduced visibility conditions"
            elif wind_mph > 20:
                threat_level = "CAUTION" 
                description = "High wind conditions"
            elif "rain" in condition or "storm" in condition:
                threat_level = "CAUTION"
                description = "Precipitation detected - exercise caution"
            elif "fog" in condition or "mist" in condition:
                threat_level = "CAUTION"
                description = "Low visibility due to atmospheric conditions"
            
            weather = {
                "temperature": temp_f,
                "humidity": humidity,
                "windSpeed": wind_mph,
                "visibility": visibility_mi,
                "condition": condition,
                "threatLevel": threat_level,
                "description": description,
                "location": "Dumfries, VA",
                "provider": "wttr.in",
                "timestamp": datetime.now().isoformat()
            }
            
            return weather
            
        except Exception as e:
            print(f"wttr.in failed: {e}")
            # Try backup weather service
            return self.get_backup_weather_data()
    
    def get_backup_weather_data(self):
        """Backup weather service using weather.gov API (no key needed for US)"""
        import urllib.request
        
        try:
            # Get weather from NOAA/NWS for Dumfries area
            # First get the grid coordinates
            point_url = "https://api.weather.gov/points/38.5768,-77.3202"
            
            with urllib.request.urlopen(point_url, timeout=10) as response:
                point_data = json.loads(response.read().decode())
            
            # Get current conditions
            stations_url = point_data['properties']['observationStations']
            
            with urllib.request.urlopen(stations_url, timeout=10) as response:
                stations_data = json.loads(response.read().decode())
            
            # Get first station's latest observation
            if stations_data['features']:
                station_url = stations_data['features'][0]['id'] + "/observations/latest"
                
                with urllib.request.urlopen(station_url, timeout=10) as response:
                    obs_data = json.loads(response.read().decode())
                
                obs = obs_data['properties']
                
                # Convert to our format
                temp_c = obs['temperature']['value']
                temp_f = int(temp_c * 9/5 + 32) if temp_c else 65
                humidity = int(obs['relativeHumidity']['value']) if obs['relativeHumidity']['value'] else 50
                wind_ms = obs['windSpeed']['value'] if obs['windSpeed']['value'] else 5
                wind_mph = int(wind_ms * 2.237) if wind_ms else 5
                visibility_m = obs['visibility']['value'] if obs['visibility']['value'] else 10000
                visibility_mi = int(visibility_m * 0.000621371) if visibility_m else 10
                
                weather = {
                    "temperature": temp_f,
                    "humidity": humidity,
                    "windSpeed": wind_mph,
                    "visibility": visibility_mi,
                    "condition": obs['textDescription'].lower() if obs['textDescription'] else "clear",
                    "threatLevel": "CLEAR",
                    "description": "Current conditions in Dumfries area",
                    "location": "Dumfries, VA (NOAA)",
                    "provider": "weather.gov",
                    "timestamp": datetime.now().isoformat()
                }
                
                return weather
                
        except Exception as e:
            print(f"NOAA weather failed: {e}")
            raise Exception("All weather services unavailable")
    
    def serve_stock_data(self):
        """Serve stock market data (simulated)"""
        stocks = {
            "wayneEnterprises": {
                "symbol": "WE",
                "price": round(random.uniform(140, 155), 2),
                "change": round(random.uniform(-5, 5), 2),
                "volume": random.randint(100000, 500000)
            },
            "techCorp": {
                "symbol": "TECH",
                "price": round(random.uniform(80, 95), 2),
                "change": round(random.uniform(-3, 3), 2),
                "volume": random.randint(50000, 200000)
            },
            "portfolio": {
                "totalValue": random.randint(2800000, 3000000),
                "dayChange": random.randint(-50000, 100000),
                "marketStatus": "CLOSED" if datetime.now().hour < 9 or datetime.now().hour > 16 else "OPEN"
            }
        }
        
        self.send_json_response(stocks)
    
    def serve_news_data(self):
        """Serve news/surveillance data"""
        news_items = [
            "GCPD reports 15% decrease in crime this quarter",
            "Wayne Enterprises announces new clean energy initiative", 
            "Arkham Asylum completes security upgrade project",
            "Gotham University breakthrough in medical research",
            "Mayor's office unveils new infrastructure plan",
            "Wayne Foundation donates $5M to local schools"
        ]
        
        activities = [
            "Perimeter scan completed - all sectors clear",
            "Traffic monitoring systems operational", 
            "Network security sweep - no threats detected",
            "Facial recognition scan - no matches found",
            "Social media monitoring - sentiment stable",
            "Emergency services coordination - all units accounted for"
        ]
        
        news = {
            "headlines": random.sample(news_items, 3),
            "recentActivity": random.choice(activities),
            "alertLevel": random.choice(["GREEN", "GREEN", "GREEN", "YELLOW"]),
            "lastScan": datetime.now().strftime("%H:%M:%S"),
            "threatCount": random.choice([0, 0, 0, 1])
        }
        
        self.send_json_response(news)
    
    def serve_schedule_data(self):
        """Serve schedule/calendar data"""
        now = datetime.now()
        
        schedule_items = [
            {
                "time": (now + timedelta(hours=1)).strftime("%H:%M"),
                "event": "East End patrol sweep",
                "status": "pending",
                "priority": "routine"
            },
            {
                "time": (now + timedelta(hours=2, minutes=30)).strftime("%H:%M"),
                "event": "Wayne Enterprises board review",
                "status": "scheduled", 
                "priority": "high"
            },
            {
                "time": (now + timedelta(minutes=45)).strftime("%H:%M"),
                "event": "Equipment maintenance check",
                "status": "routine",
                "priority": "low"
            }
        ]
        
        self.send_json_response({
            "items": schedule_items,
            "priorityLevel": random.choice(["LOW", "LOW", "MEDIUM"]),
            "totalEvents": len(schedule_items)
        })
    
    def serve_briefing_data(self):
        """Serve AI briefing data"""
        briefings = [
            "Good evening, Master Bruce. All systems operational and Gotham appears secure.",
            "Sir, tonight's surveillance shows no significant criminal activity. Perfect for strategic planning.",
            "All quiet on the western front, Master Bruce. GCPD reports routine patrols only.",
            "Evening briefing: Finances stable, weather optimal, equipment ready. The city rests peacefully.",
            "Master Bruce, network scans show no unusual activity. Consider this a well-deserved quiet evening.",
            "Sir, all cave systems functioning at optimal levels. Ready for whatever the night may bring."
        ]
        
        current_hour = datetime.now().hour
        time_context = "morning" if current_hour < 12 else "afternoon" if current_hour < 18 else "evening"
        
        briefing = {
            "message": random.choice(briefings),
            "timeContext": time_context,
            "systemStatus": "OPTIMAL",
            "timestamp": datetime.now().isoformat(),
            "priority": "ROUTINE"
        }
        
        self.send_json_response(briefing)
    
    def send_json_response(self, data):
        """Send JSON response with CORS headers"""
        response = json.dumps(data, indent=2)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response.encode())
    
    def send_json_error(self, code, message):
        """Send JSON error response"""
        error_data = {"error": message, "code": code}
        response = json.dumps(error_data)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response.encode())

def run_server(port=8080):
    """Run the Batcave dashboard server"""
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, BatcaveHandler)
    
    print(f"🦇 Alfred's Batcave Command Center")
    print(f"📍 Server running on port {port}")
    print(f"🌐 Local: http://localhost:{port}")
    print(f"🌐 Tailscale: http://100.122.252.21:{port}")
    print(f"🎭 Master Bruce, your command center awaits...")
    print("\\n🔧 API Endpoints:")
    print("   • /api/weather - Weather and environmental data")
    print("   • /api/stocks - Financial market information") 
    print("   • /api/news - Surveillance and news updates")
    print("   • /api/schedule - Mission schedule and calendar")
    print("   • /api/briefing - AI briefing messages")
    print("\\nPress Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\\n🛑 Batcave systems offline. Good night, Master Bruce.")
        httpd.shutdown()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)