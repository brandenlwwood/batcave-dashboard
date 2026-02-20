"""
Alfred's Batcave Command Center v2 — FastAPI Server
Real-time dashboard with WebSocket updates
Phase 1: Cameras, Weather, Infra, Kanban, Health, Frigate
Phase 2: Lights, Scenes, Media Players, Voice, Family Activities
"""

import os
import json
import asyncio
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
import httpx

app = FastAPI(title="Batcave Command Center")

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_json(message)
            except:
                dead.add(ws)
        self.active -= dead

manager = ConnectionManager()

# --- Config ---
HA_URL = os.getenv("HA_URL", "http://10.10.1.170:8123")
HA_TOKEN = ""
FRIGATE_URL = os.getenv("FRIGATE_URL", "http://10.10.1.170:5000")
REOLINK_URL = os.getenv("REOLINK_URL", "http://10.10.1.129")
REOLINK_USER = os.getenv("REOLINK_USER", "admin")
REOLINK_PASS = os.getenv("REOLINK_PASS", "")
MIKROTIK_HOST = os.getenv("MIKROTIK_HOST", "10.10.1.1")
MIKROTIK_USER = os.getenv("MIKROTIK_USER", "admin")
MIKROTIK_PASS = os.getenv("MIKROTIK_PASS", "")
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY", "")
MERAKI_NET_ID = os.getenv("MERAKI_NET_ID", "")
MERAKI_ORG_ID = os.getenv("MERAKI_ORG_ID", "1716645")

KANBAN_FILE = Path("/app/data/kanban.json")
STATIC_DIR = Path(__file__).parent / "static"

# Load HA token
ha_token_file = os.getenv("HA_TOKEN_FILE", "/app/.ha_token")
if Path(ha_token_file).exists():
    HA_TOKEN = Path(ha_token_file).read_text().strip()

HA_HEADERS = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"} if HA_TOKEN else {}

# Light grouping — map entity_ids to rooms (skip segments)
LIGHT_ROOMS = {
    "Theater": ["light.ai_sync_box_kit", "light.screen_lights", "light.side_projector"],
    "Office": ["light.office"],
    "Garage": ["light.small_garage_light", "light.big_garage_left_light", "light.big_garage_right"],
    "Bathroom": ["light.bathroom_vanity_left", "light.bathroom_vanity_middle", "light.bathroom_vanity_right"],
    "Outside": ["light.deck_light", "light.porch_light", "light.patio_light"],
    "Downlights": ["light.smart_led_downlight", "light.smart_led_downlight_2", "light.smart_led_downlight_3", "light.smart_led_downlight_4"],
}

# Scene icons
SCENE_ICONS = {
    "movie_night": "🎬",
    "theater_bright": "💡",
    "goodnight": "🌙",
    "outside_lights_on": "🏠",
    "outside_lights_off": "🌑",
    "gaming_mode": "🎮",
    "bar_on": "🍸",
}


# ============================================================
# API Routes — Phase 1
# ============================================================

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    mem_stats = {"status": "unknown"}
    try:
        result = await run_command("bash /home/wood/.openclaw/workspace/skills/memory-manager/detect.sh 2>/dev/null | tail -5")
        if "Healthy" in result:
            mem_stats["status"] = "healthy"
        elif "WARNING" in result:
            mem_stats["status"] = "warning"
        elif "CRITICAL" in result:
            mem_stats["status"] = "critical"
        mem_stats["raw"] = result.strip()
    except:
        pass
    return {"timestamp": datetime.now().isoformat(), "memory": mem_stats, "uptime": get_uptime()}


@app.get("/api/weather")
async def weather():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get("https://wttr.in/Dumfries+VA+22026?format=j1")
            data = resp.json()
            current = data.get("current_condition", [{}])[0]
            forecast = data.get("weather", [])
            temp_f = current.get("temp_F", "?")
            feels_like = current.get("FeelsLikeF", "?")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
            humidity = current.get("humidity", "?")
            wind_mph = current.get("windspeedMiles", "?")
            uv = current.get("uvIndex", "?")
            suggestion = get_activity_suggestion(
                int(temp_f) if temp_f != "?" else 70, desc.lower(),
                int(uv) if uv != "?" else 5, datetime.now().strftime("%A")
            )
            today_forecast = forecast[0] if forecast else {}
            tomorrow_forecast = forecast[1] if len(forecast) > 1 else {}
            return {
                "current": {"temp_f": temp_f, "feels_like": feels_like, "description": desc,
                            "humidity": humidity, "wind_mph": wind_mph, "uv_index": uv},
                "today": {"high": today_forecast.get("maxtempF", "?"), "low": today_forecast.get("mintempF", "?"),
                           "sunrise": today_forecast.get("astronomy", [{}])[0].get("sunrise", ""),
                           "sunset": today_forecast.get("astronomy", [{}])[0].get("sunset", "")},
                "tomorrow": {"high": tomorrow_forecast.get("maxtempF", "?"), "low": tomorrow_forecast.get("mintempF", "?"),
                             "desc": tomorrow_forecast.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "?") if tomorrow_forecast.get("hourly") else "?"},
                "suggestion": suggestion,
            }
        except Exception as e:
            return {"error": str(e)}


@app.get("/api/cameras/{channel}")
async def camera_snapshot(channel: int):
    url = f"{REOLINK_URL}/cgi-bin/api.cgi?cmd=Snap&channel={channel}&rs=abc123&user={REOLINK_USER}&password={REOLINK_PASS}"
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(url)
            return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"),
                          headers={"Cache-Control": "no-cache"})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/api/frigate/events")
async def frigate_events():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{FRIGATE_URL}/api/events", params={"limit": 20, "has_clip": 1})
            events = resp.json()
            return [{"id": e.get("id"), "camera": e.get("camera"), "label": e.get("label"),
                     "score": round(e.get("top_score") or e.get("data", {}).get("score", 0) or 0, 2), "start": e.get("start_time"),
                     "end": e.get("end_time"), "thumbnail": f"/api/frigate/thumb/{e['id']}",
                     "clip": f"/api/frigate/clip/{e['id']}"} for e in events]
        except Exception as e:
            return JSONResponse({"error": str(e), "events": []}, status_code=200)


@app.get("/api/frigate/thumb/{event_id}")
async def frigate_thumbnail(event_id: str):
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(f"{FRIGATE_URL}/api/events/{event_id}/thumbnail.jpg")
            return Response(content=resp.content, media_type="image/jpeg")
        except:
            return Response(status_code=404)




@app.get("/api/frigate/clip/{event_id}")
async def frigate_clip(event_id: str):
    """Proxy Frigate event clips so they work externally"""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{FRIGATE_URL}/api/events/{event_id}/clip.mp4")
            return Response(
                content=resp.content,
                media_type="video/mp4",
                headers={"Cache-Control": "public, max-age=3600"}
            )
        except Exception as e:
            return Response(status_code=502)

@app.get("/api/infra/status")
async def infra_status():
    checks = {}
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            checks["unraid"] = {"status": await tcp_check("10.10.1.6", 22), "ip": "10.10.1.6"}
        except:
            checks["unraid"] = {"status": "unknown", "ip": "10.10.1.6"}
        try:
            checks["proxmox"] = {"status": await tcp_check("10.10.1.23", 8006), "ip": "10.10.1.23"}
        except:
            checks["proxmox"] = {"status": "unknown", "ip": "10.10.1.23"}
        try:
            resp = await client.get(f"http://{MIKROTIK_HOST}/rest/system/resource", auth=(MIKROTIK_USER, MIKROTIK_PASS))
            if resp.status_code == 200:
                data = resp.json()
                checks["mikrotik"] = {"status": "online", "ip": MIKROTIK_HOST, "uptime": data.get("uptime", "?"),
                    "cpu_load": data.get("cpu-load", "?"),
                    "memory_used": round((int(data.get("total-memory", 1)) - int(data.get("free-memory", 0))) / int(data.get("total-memory", 1)) * 100),
                    "version": data.get("version", "?")}
            else:
                checks["mikrotik"] = {"status": "degraded", "ip": MIKROTIK_HOST}
        except:
            checks["mikrotik"] = {"status": "offline", "ip": MIKROTIK_HOST}
        try:
            resp = await client.get(f"https://api.meraki.com/api/v1/organizations/{MERAKI_ORG_ID}/devices/statuses",
                                    headers={"X-Cisco-Meraki-API-Key": MERAKI_API_KEY})
            if resp.status_code == 200:
                devices = resp.json()
                online = sum(1 for d in devices if d.get("status") == "online")
                checks["meraki"] = {"status": "online", "devices_total": len(devices), "devices_online": online}
            else:
                checks["meraki"] = {"status": "degraded"}
        except:
            checks["meraki"] = {"status": "unknown"}
        try:
            resp = await client.get(f"{HA_URL}/api/", headers=HA_HEADERS)
            checks["homeassistant"] = {"status": "online" if resp.status_code == 200 else "degraded", "ip": "10.10.1.170"}
        except:
            checks["homeassistant"] = {"status": "offline", "ip": "10.10.1.170"}
        try:
            resp = await client.get(f"{FRIGATE_URL}/api/stats")
            if resp.status_code == 200:
                stats = resp.json()
                checks["frigate"] = {"status": "online", "cameras": len(stats.get("cameras", {}))}
            else:
                checks["frigate"] = {"status": "degraded"}
        except:
            checks["frigate"] = {"status": "offline"}
    return checks


@app.get("/api/kanban")
async def get_kanban():
    if KANBAN_FILE.exists():
        return json.loads(KANBAN_FILE.read_text())
    return {"todo": [], "in_progress": [], "done": []}


@app.post("/api/kanban")
async def update_kanban(data: dict):
    KANBAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    KANBAN_FILE.write_text(json.dumps(data, indent=2))
    await manager.broadcast({"type": "kanban_update", "data": data})
    return {"status": "ok"}


# ============================================================
# API Routes — Phase 2: Lights, Scenes, Media, Activities
# ============================================================

@app.get("/api/ha/lights")
async def ha_lights():
    """Get lights grouped by room"""
    if not HA_TOKEN:
        return {"error": "No HA token"}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{HA_URL}/api/states", headers=HA_HEADERS)
            states = {s["entity_id"]: s for s in resp.json()}
            rooms = {}
            for room, entities in LIGHT_ROOMS.items():
                lights = []
                for eid in entities:
                    if eid in states:
                        s = states[eid]
                        attrs = s["attributes"]
                        lights.append({
                            "entity_id": eid,
                            "name": attrs.get("friendly_name", eid.split(".")[-1]),
                            "state": s["state"],
                            "brightness": attrs.get("brightness"),
                            "rgb_color": attrs.get("rgb_color"),
                            "color_temp": attrs.get("color_temp"),
                        })
                if lights:
                    any_on = any(l["state"] == "on" for l in lights)
                    rooms[room] = {"lights": lights, "any_on": any_on}
            return rooms
        except Exception as e:
            return {"error": str(e)}


@app.post("/api/ha/light/toggle")
async def ha_light_toggle(request: Request):
    """Toggle a light or all lights in a room"""
    body = await request.json()
    entity_id = body.get("entity_id")
    room = body.get("room")
    action = body.get("action", "toggle")  # on, off, toggle

    if not HA_TOKEN:
        return {"error": "No HA token"}

    targets = []
    if room and room in LIGHT_ROOMS:
        targets = LIGHT_ROOMS[room]
    elif entity_id:
        targets = [entity_id]
    else:
        return {"error": "Need entity_id or room"}

    service = f"light/turn_{action}" if action in ("on", "off") else "light/toggle"

    async with httpx.AsyncClient(timeout=10) as client:
        results = []
        for eid in targets:
            try:
                payload = {"entity_id": eid}
                if body.get("brightness") is not None:
                    payload["brightness"] = body["brightness"]
                if body.get("rgb_color") is not None:
                    payload["rgb_color"] = body["rgb_color"]
                resp = await client.post(f"{HA_URL}/api/services/{service}",
                                        headers=HA_HEADERS, json=payload)
                results.append({"entity_id": eid, "status": resp.status_code})
            except Exception as e:
                results.append({"entity_id": eid, "error": str(e)})
    return {"results": results}


@app.get("/api/ha/scenes")
async def ha_scenes():
    if not HA_TOKEN:
        return {"error": "No HA token"}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{HA_URL}/api/states", headers=HA_HEADERS)
            states = resp.json()
            scenes = []
            for s in states:
                if s["entity_id"].startswith("scene."):
                    name = s["attributes"].get("friendly_name", s["entity_id"])
                    # Find icon
                    icon = "🎭"
                    for key, emoji in SCENE_ICONS.items():
                        if key in s["entity_id"]:
                            icon = emoji
                            break
                    scenes.append({"entity_id": s["entity_id"], "name": name, "icon": icon})
            return scenes
        except Exception as e:
            return {"error": str(e)}


@app.post("/api/ha/scene/{entity_id:path}")
async def trigger_ha_scene(entity_id: str):
    if not HA_TOKEN:
        return {"error": "No HA token"}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(f"{HA_URL}/api/services/scene/turn_on",
                                    headers=HA_HEADERS, json={"entity_id": entity_id})
            return {"status": "ok", "code": resp.status_code}
        except Exception as e:
            return {"error": str(e)}


@app.get("/api/ha/media_players")
async def ha_media_players():
    """Get all media players with now-playing info"""
    if not HA_TOKEN:
        return {"error": "No HA token"}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{HA_URL}/api/states", headers=HA_HEADERS)
            states = resp.json()
            players = []
            for s in states:
                if not s["entity_id"].startswith("media_player."):
                    continue
                attrs = s["attributes"]
                players.append({
                    "entity_id": s["entity_id"],
                    "name": attrs.get("friendly_name", s["entity_id"].split(".")[-1]),
                    "state": s["state"],
                    "media_title": attrs.get("media_title"),
                    "media_artist": attrs.get("media_artist"),
                    "media_content_type": attrs.get("media_content_type"),
                    "volume_level": attrs.get("volume_level"),
                    "is_volume_muted": attrs.get("is_volume_muted", False),
                    "app_name": attrs.get("app_name"),
                    "entity_picture": attrs.get("entity_picture"),
                })
            return players
        except Exception as e:
            return {"error": str(e)}


@app.post("/api/ha/media/control")
async def ha_media_control(request: Request):
    """Control a media player"""
    body = await request.json()
    entity_id = body.get("entity_id")
    action = body.get("action")  # play_pause, volume_up, volume_down, volume_set, mute, next, previous

    if not HA_TOKEN or not entity_id or not action:
        return {"error": "Missing params"}

    service_map = {
        "play_pause": "media_player/media_play_pause",
        "play": "media_player/media_play",
        "pause": "media_player/media_pause",
        "stop": "media_player/media_stop",
        "next": "media_player/media_next_track",
        "previous": "media_player/media_previous_track",
        "volume_up": "media_player/volume_up",
        "volume_down": "media_player/volume_down",
        "volume_set": "media_player/volume_set",
        "mute": "media_player/volume_mute",
    }

    service = service_map.get(action)
    if not service:
        return {"error": f"Unknown action: {action}"}

    payload = {"entity_id": entity_id}
    if action == "volume_set" and body.get("volume") is not None:
        payload["volume_level"] = body["volume"]
    if action == "mute":
        payload["is_volume_muted"] = body.get("mute", True)

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(f"{HA_URL}/api/services/{service}",
                                    headers=HA_HEADERS, json=payload)
            return {"status": "ok", "code": resp.status_code}
        except Exception as e:
            return {"error": str(e)}


@app.get("/api/activities")
async def family_activities():
    """Smart family activity suggestions — weather-aware, day-aware, age-appropriate"""
    # Get weather data
    wx = {}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get("https://wttr.in/Dumfries+VA+22026?format=j1")
            data = resp.json()
            current = data.get("current_condition", [{}])[0]
            wx["temp"] = int(current.get("temp_F", 70))
            wx["desc"] = current.get("weatherDesc", [{}])[0].get("value", "").lower()
            wx["uv"] = int(current.get("uvIndex", 5))
            wx["wind"] = int(current.get("windspeedMiles", 0))
        except:
            wx = {"temp": 70, "desc": "clear", "uv": 5, "wind": 5}

    now = datetime.now()
    day = now.strftime("%A")
    hour = now.hour
    is_weekend = day in ("Saturday", "Sunday")
    is_evening = hour >= 17
    is_nice = wx["temp"] > 50 and "rain" not in wx["desc"] and "snow" not in wx["desc"]
    is_hot = wx["temp"] > 85
    is_cold = wx["temp"] < 40

    activities = []

    # --- Outdoor activities (weather permitting) ---
    if is_nice and not is_hot:
        activities.append({"title": "Bike ride on Occoquan Trail", "icon": "🚴", "category": "outdoor",
                          "detail": f"{wx['temp']}°F and {wx['desc']} — perfect conditions", "for": "family"})
        if is_weekend:
            activities.append({"title": "Hike at Prince William Forest Park", "icon": "🥾", "category": "outdoor",
                              "detail": "12+ miles of trails, bring water", "for": "family"})
            activities.append({"title": "Walk around Old Town Occoquan", "icon": "🏘️", "category": "outdoor",
                              "detail": "Shops, ice cream, river views", "for": "family"})
        if wx["temp"] > 75:
            activities.append({"title": "Splash pad or pool time", "icon": "🏊", "category": "outdoor",
                              "detail": "Andrew Leitch Park or neighborhood pool", "for": "kids"})
    elif is_cold:
        activities.append({"title": "Hot chocolate run", "icon": "☕", "category": "outdoor",
                          "detail": "Drive to a cozy cafe, warm up together", "for": "family"})

    # --- Indoor activities ---
    if is_evening or not is_nice:
        activities.append({"title": "Movie night", "icon": "🎬", "category": "indoor",
                          "detail": "Fire up the projector, popcorn time", "for": "family"})
        activities.append({"title": "Board game tournament", "icon": "🎲", "category": "indoor",
                          "detail": "Settlers of Catan, Ticket to Ride, or card games", "for": "family"})

    activities.append({"title": "Homemade pizza night", "icon": "🍕", "category": "indoor",
                      "detail": "Everyone picks their own toppings", "for": "family"})

    if is_evening:
        activities.append({"title": "Baking challenge", "icon": "🧁", "category": "indoor",
                          "detail": "Who can make the best cookies/brownies?", "for": "kids"})

    # --- Teen-specific (14 + 12 year olds) ---
    if is_weekend:
        activities.append({"title": "Escape room", "icon": "🔐", "category": "outing",
                          "detail": "Breakout Games or Escapology in Woodbridge", "for": "teens"})
        activities.append({"title": "Laser tag / trampoline park", "icon": "🎯", "category": "outing",
                          "detail": "Sky Zone or TopGolf", "for": "teens"})
        if is_nice:
            activities.append({"title": "Mini golf at Topgolf", "icon": "⛳", "category": "outing",
                              "detail": "Good for all ages + food", "for": "family"})

    # --- Couple (Sandy + Branden) ---
    if is_evening and (day == "Friday" or day == "Saturday"):
        activities.append({"title": "Date night at a local restaurant", "icon": "🍷", "category": "date",
                          "detail": "Madigan's, Tim's Rivershore, or Fiore di Luna", "for": "couple"})

    # --- Day-specific ---
    if day == "Friday":
        activities.append({"title": "Friday movie night!", "icon": "🍿", "category": "tradition",
                          "detail": "Pick a new release, order takeout", "for": "family"})
    if day == "Sunday":
        activities.append({"title": "Sunday meal prep together", "icon": "🥗", "category": "indoor",
                          "detail": "Get the week started right", "for": "family"})

    # UV warning
    if wx["uv"] > 7 and is_nice:
        activities.insert(0, {"title": "⚠️ High UV Index", "icon": "☀️", "category": "warning",
                             "detail": f"UV is {wx['uv']} — sunscreen required outside!", "for": "all"})

    return {
        "weather": {"temp": wx["temp"], "desc": wx["desc"], "is_nice": is_nice},
        "day": day,
        "time_of_day": "evening" if is_evening else "daytime",
        "activities": activities[:10],
    }


@app.post("/api/chat")
async def chat_message(request: Request):
    """Send a message to Alfred via Telegram relay (proxy to OpenClaw)"""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return {"error": "Empty message"}
    # For now, return acknowledgment. Full Telegram integration would need bot token.
    return {"status": "received", "message": message, "note": "Relay to Alfred pending Telegram bot integration"}


# ============================================================
# WebSocket
# ============================================================


# ============================================================
# API Routes — Phase 3: News, Network Topology, Speedtest, Notifications, Timers
# ============================================================

@app.get("/api/news")
async def news_feed():
    """Curated news ticker — eBPF, federal IT, Cisco, competitors"""
    topics = [
        ("eBPF Cilium cloud native networking", "ebpf"),
        ("federal IT cybersecurity contracts 2026", "federal"),
        ("Cisco Hypershield security", "cisco"),
        ("zero trust microsegmentation federal", "zerotrust"),
    ]
    # Rotate topic based on hour
    hour = datetime.now().hour
    topic_query, topic_tag = topics[hour % len(topics)]
    
    articles = []
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            # Use Brave Search API
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": topic_query, "count": 8, "freshness": "pw"},
                headers={"X-Subscription-Token": os.getenv("BRAVE_API_KEY", ""), "Accept": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                for r in data.get("web", {}).get("results", [])[:8]:
                    articles.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "description": r.get("description", "")[:200],
                        "age": r.get("age", ""),
                        "source": r.get("meta_url", {}).get("hostname", ""),
                        "tag": topic_tag,
                    })
        except Exception as e:
            pass
    
    # If Brave fails or no key, try scraping a simple news source
    if not articles:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://news.google.com/rss/search?q={topic_query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en")
                if resp.status_code == 200:
                    import re
                    items = re.findall(r'<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<source.*?>(.*?)</source>.*?</item>', resp.text, re.DOTALL)
                    for title, url, source in items[:8]:
                        # Clean CDATA
                        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title).strip()
                        articles.append({
                            "title": title,
                            "url": url.strip(),
                            "description": "",
                            "age": "",
                            "source": source.strip(),
                            "tag": topic_tag,
                        })
        except:
            pass
    
    return {"topic": topic_tag, "query": topic_query, "articles": articles}


@app.get("/api/network/topology")
async def network_topology():
    """Network topology — MikroTik interfaces + Meraki devices + DHCP leases"""
    topology = {"router": None, "vlans": [], "meraki_devices": [], "dhcp_leases": [], "interfaces": []}
    
    async with httpx.AsyncClient(timeout=10) as client:
        # MikroTik router info
        try:
            resp = await client.get(f"http://{MIKROTIK_HOST}/rest/system/resource",
                                   auth=(MIKROTIK_USER, MIKROTIK_PASS))
            if resp.status_code == 200:
                data = resp.json()
                topology["router"] = {
                    "name": data.get("board-name", "RB5009"),
                    "version": data.get("version", "?"),
                    "cpu_load": data.get("cpu-load", 0),
                    "uptime": data.get("uptime", "?"),
                    "memory_pct": round((int(data.get("total-memory", 1)) - int(data.get("free-memory", 0))) / int(data.get("total-memory", 1)) * 100),
                }
        except:
            topology["router"] = {"name": "RB5009", "version": "?", "cpu_load": 0, "uptime": "?", "memory_pct": 0}

        # MikroTik interfaces
        try:
            resp = await client.get(f"http://{MIKROTIK_HOST}/rest/interface",
                                   auth=(MIKROTIK_USER, MIKROTIK_PASS))
            if resp.status_code == 200:
                for iface in resp.json():
                    if iface.get("type") in ("ether", "vlan", "bridge") and iface.get("disabled") != "true":
                        topology["interfaces"].append({
                            "name": iface.get("name", ""),
                            "type": iface.get("type", ""),
                            "running": iface.get("running", False),
                            "speed": iface.get("link-speed", ""),
                            "rx_bytes": int(iface.get("rx-byte", 0)),
                            "tx_bytes": int(iface.get("tx-byte", 0)),
                        })
        except:
            pass

        # MikroTik VLANs via IP addresses
        try:
            resp = await client.get(f"http://{MIKROTIK_HOST}/rest/ip/address",
                                   auth=(MIKROTIK_USER, MIKROTIK_PASS))
            if resp.status_code == 200:
                vlan_names = {"vlan1-main": "Main", "vlan2-personal": "WayneManor", "vlan3-iot": "Beast",
                             "vlan4-guest": "Lion-O", "vlan5-vpn": "VPN", "bridge1": "Bridge"}
                for addr in resp.json():
                    iface = addr.get("interface", "")
                    topology["vlans"].append({
                        "interface": iface,
                        "name": vlan_names.get(iface, iface),
                        "address": addr.get("address", ""),
                        "network": addr.get("network", ""),
                    })
        except:
            pass

        # MikroTik DHCP leases
        try:
            resp = await client.get(f"http://{MIKROTIK_HOST}/rest/ip/dhcp-server/lease",
                                   auth=(MIKROTIK_USER, MIKROTIK_PASS))
            if resp.status_code == 200:
                for lease in resp.json():
                    if lease.get("status") == "bound":
                        topology["dhcp_leases"].append({
                            "address": lease.get("address", ""),
                            "hostname": lease.get("host-name", "unknown"),
                            "mac": lease.get("mac-address", ""),
                            "server": lease.get("server", ""),
                        })
        except:
            pass

        # Meraki devices
        try:
            resp = await client.get(
                f"https://api.meraki.com/api/v1/organizations/{MERAKI_ORG_ID}/devices/statuses",
                headers={"X-Cisco-Meraki-API-Key": MERAKI_API_KEY}
            )
            if resp.status_code == 200:
                for dev in resp.json():
                    topology["meraki_devices"].append({
                        "name": dev.get("name", dev.get("serial", "?")),
                        "model": dev.get("model", "?"),
                        "status": dev.get("status", "unknown"),
                        "ip": dev.get("lanIp", ""),
                        "mac": dev.get("mac", ""),
                        "serial": dev.get("serial", ""),
                    })
        except:
            pass

    return topology


@app.get("/api/speedtest/history")
async def speedtest_history():
    """Get speedtest history from stored results"""
    speedtest_file = Path("/app/data/speedtest_history.json")
    if speedtest_file.exists():
        try:
            return json.loads(speedtest_file.read_text())
        except:
            return {"results": []}
    return {"results": []}


@app.post("/api/speedtest/run")
async def speedtest_run():
    """Run a speedtest and store results"""
    try:
        result = await run_command("speedtest-cli --json 2>/dev/null || speedtest --format=json 2>/dev/null")
        if result.strip():
            data = json.loads(result)
            # Normalize — speedtest-cli vs ookla speedtest have different formats
            entry = {
                "timestamp": datetime.now().isoformat(),
                "download_mbps": round(data["download"] / 1_000_000, 1) if isinstance(data.get("download"), (int, float)) else round(data.get("download", {}).get("bandwidth", 0) * 8 / 1_000_000, 1),
                "upload_mbps": round(data["upload"] / 1_000_000, 1) if isinstance(data.get("upload"), (int, float)) else round(data.get("upload", {}).get("bandwidth", 0) * 8 / 1_000_000, 1),
                "ping_ms": round(data["ping"], 1) if isinstance(data.get("ping"), (int, float)) else round(data.get("ping", {}).get("latency", 0), 1),
                "server": data.get("server", {}).get("name", "?") if isinstance(data.get("server"), dict) else str(data.get("server", "?")),
            }
            
            # Append to history
            history_file = Path("/app/data/speedtest_history.json")
            history = {"results": []}
            if history_file.exists():
                try:
                    history = json.loads(history_file.read_text())
                except:
                    pass
            history["results"].append(entry)
            # Keep last 100
            history["results"] = history["results"][-100:]
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history_file.write_text(json.dumps(history, indent=2))
            
            return {"status": "ok", "result": entry}
        return {"error": "speedtest not available"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/notifications")
async def notifications():
    """Get notification history"""
    notif_file = Path("/app/data/notifications.json")
    if notif_file.exists():
        try:
            data = json.loads(notif_file.read_text())
            return data
        except:
            pass
    return {"notifications": []}


@app.post("/api/notifications")
async def add_notification(request: Request):
    """Add a notification"""
    body = await request.json()
    notif_file = Path("/app/data/notifications.json")
    notif_file.parent.mkdir(parents=True, exist_ok=True)
    
    data = {"notifications": []}
    if notif_file.exists():
        try:
            data = json.loads(notif_file.read_text())
        except:
            pass
    
    notif = {
        "id": str(int(datetime.now().timestamp() * 1000)),
        "title": body.get("title", ""),
        "message": body.get("message", ""),
        "type": body.get("type", "info"),  # info, warning, success, error
        "timestamp": datetime.now().isoformat(),
        "read": False,
    }
    data["notifications"].insert(0, notif)
    data["notifications"] = data["notifications"][:50]  # Keep last 50
    notif_file.write_text(json.dumps(data, indent=2))
    
    await manager.broadcast({"type": "notification", "data": notif})
    return {"status": "ok", "notification": notif}


@app.post("/api/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str):
    """Mark a notification as read"""
    notif_file = Path("/app/data/notifications.json")
    if notif_file.exists():
        data = json.loads(notif_file.read_text())
        for n in data.get("notifications", []):
            if n["id"] == notif_id:
                n["read"] = True
        notif_file.write_text(json.dumps(data, indent=2))
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except:
        manager.disconnect(ws)


# ============================================================
# Background Tasks
# ============================================================

@app.on_event("startup")
async def startup():
    asyncio.create_task(periodic_updates())


async def periodic_updates():
    """Push periodic updates to all connected clients"""
    tick = 0
    while True:
        try:
            if manager.active:
                await manager.broadcast({"type": "time", "timestamp": datetime.now().isoformat()})
                # Push light states every 10s
                if tick % 1 == 0:
                    try:
                        lights = await ha_lights()
                        if not isinstance(lights, dict) or "error" not in lights:
                            await manager.broadcast({"type": "lights_update", "data": lights})
                    except:
                        pass
                # Push media player states every 10s
                if tick % 1 == 0:
                    try:
                        players = await ha_media_players()
                        if isinstance(players, list):
                            await manager.broadcast({"type": "media_update", "data": players})
                    except:
                        pass
                tick += 1
        except:
            pass
        await asyncio.sleep(10)


# ============================================================
# Helpers
# ============================================================

def get_activity_suggestion(temp, desc, uv, day):
    suggestions = []
    is_weekend = day in ("Saturday", "Sunday")
    is_nice = temp > 50 and "rain" not in desc and "snow" not in desc
    if is_nice and temp > 65:
        suggestions.append("🚴 Bike ride on Occoquan Trail")
        suggestions.append("🏊 Pool or splash pad")
        if is_weekend:
            suggestions.append("🥾 Prince William Forest hike")
    elif is_nice:
        suggestions.append("🚶 Walk around Occoquan")
        suggestions.append("☕ Hot chocolate + Old Town")
    else:
        suggestions.append("🎬 Movie marathon")
        suggestions.append("🎮 Family game night")
        suggestions.append("🍕 Homemade pizza night")
    if day == "Friday":
        suggestions.append("🍿 Friday movie night!")
    if uv > 7:
        suggestions.append("⚠️ High UV — sunscreen!")
    return suggestions[:4]


async def tcp_check(host, port, timeout=2.0):
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return "online"
    except:
        return "offline"


def get_uptime():
    try:
        with open("/proc/uptime") as f:
            s = float(f.read().split()[0])
            return f"{int(s//86400)}d {int((s%86400)//3600)}h"
    except:
        return "unknown"


async def run_command(cmd):
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    return stdout.decode()


# --- Static files (mount last) ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")
