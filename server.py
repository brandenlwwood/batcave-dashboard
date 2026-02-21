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

import sqlite3
import secrets

import jwt as pyjwt
import bcrypt

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

# --- Auth System ---
AUTH_DATA_DIR = Path("/app/data")
AUTH_DB_PATH = AUTH_DATA_DIR / "users.db"
JWT_SECRET_FILE = AUTH_DATA_DIR / ".jwt_secret"
LABELS_FILE = AUTH_DATA_DIR / "widget_labels.json"
PERMISSIONS_FILE = AUTH_DATA_DIR / "user_permissions.json"
JWT_EXPIRY_DAYS = 7

WIDGET_DEFAULTS = {
    "widget-weather": "WEATHER", "widget-calendar": "FAMILY CALENDAR",
    "widget-cameras": "CAMERAS", "widget-security": "SECURITY OPS",
    "widget-scenes": "PROTOCOLS", "widget-lights": "LIGHTING ARRAY",
    "widget-activities": "FAMILY OPS", "widget-media": "MEDIA ARRAY",
    "widget-media-center": "MEDIA COMMAND", "widget-infra": "SYSTEMS STATUS",
    "widget-health": "ALFRED NEURAL NET", "widget-frigate": "MOTION DETECTION",
    "widget-topology": "NETWORK MAP", "widget-speedtest": "BANDWIDTH",
    "widget-notifications": "ALERT LOG", "widget-timers": "QUICK TIMERS",
    "widget-chat": "ALFRED TERMINAL", "widget-kanban": "MISSION BOARD",
}


# --- Login Rate Limiting ---
_login_attempts = {}  # ip -> (count, first_attempt_time)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes

def _check_rate_limit(ip):
    import time
    now = time.time()
    if ip in _login_attempts:
        count, first = _login_attempts[ip]
        if now - first > LOGIN_WINDOW_SECONDS:
            _login_attempts[ip] = (1, now)
            return True
        if count >= LOGIN_MAX_ATTEMPTS:
            return False
        _login_attempts[ip] = (count + 1, first)
        return True
    _login_attempts[ip] = (1, now)
    return True

def _reset_rate_limit(ip):
    _login_attempts.pop(ip, None)

def _jwt_secret():
    if JWT_SECRET_FILE.exists():
        return JWT_SECRET_FILE.read_text().strip()
    s = secrets.token_hex(32)
    JWT_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    JWT_SECRET_FILE.write_text(s)
    return s

def _init_users_db():
    AUTH_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUTH_DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL, display_name TEXT, role TEXT DEFAULT 'user',
        created_at TEXT, last_login TEXT)""")
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        h = bcrypt.hashpw(b"batcave", bcrypt.gensalt()).decode()
        conn.execute("INSERT INTO users (username,password_hash,display_name,role,created_at) VALUES (?,?,?,?,?)",
                     ("admin", h, "Administrator", "admin", datetime.now().isoformat()))
        conn.commit()
        print(">>> Auto-created admin user (password: batcave)")
    conn.close()

def _db():
    c = sqlite3.connect(str(AUTH_DB_PATH))
    c.row_factory = sqlite3.Row
    return c

def _make_token(uid, uname, role):
    return pyjwt.encode({"user_id": uid, "username": uname, "role": role,
                         "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)},
                        _jwt_secret(), algorithm="HS256")

def _decode_token(tok):
    try:
        return pyjwt.decode(tok, _jwt_secret(), algorithms=["HS256"])
    except:
        return None

def _current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _decode_token(auth[7:])
    return None

def _get_labels():
    if LABELS_FILE.exists():
        try: return json.loads(LABELS_FILE.read_text())
        except: pass
    return {}

def _get_all_permissions():
    if PERMISSIONS_FILE.exists():
        try: return json.loads(PERMISSIONS_FILE.read_text())
        except: pass
    return {}


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



# --- Auth Middleware ---
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as StarletteRedirect, JSONResponse as StarletteJSON

class AuthMiddleware(BaseHTTPMiddleware):
    OPEN_PATHS = {"/login", "/login.html", "/api/auth/login", "/favicon.ico"}
    OPEN_PREFIXES = ("/static/", "/css/", "/js/", "/img/", "/fonts/")

    async def dispatch(self, request, call_next):
        path = request.url.path
        # Allow open paths
        if path in self.OPEN_PATHS or any(path.startswith(p) for p in self.OPEN_PREFIXES):
            return await call_next(request)
        # Allow websocket
        if path == "/ws":
            return await call_next(request)
        # API endpoints need auth (except login)
        if path.startswith("/api/"):
            user = _current_user(request)
            if not user:
                return StarletteJSON({"error": "Unauthorized"}, status_code=401)
            # Admin endpoints need admin role
            if path.startswith("/api/admin/") and user.get("role") != "admin":
                return StarletteJSON({"error": "Forbidden"}, status_code=403)
            return await call_next(request)
        # Admin page auth handled client-side (JS checks role via /api/auth/me)
        # Server-side redirect doesn't work because browser nav has no Authorization header
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# ============================================================
# API Routes — Phase 1
# ============================================================


@app.get("/login")
async def login_page():
    return FileResponse(STATIC_DIR / "login.html")

@app.get("/admin")
async def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")




# ============================================================
# Auth & Admin API Routes
# ============================================================

@app.post("/api/auth/login")
async def auth_login(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse({"error": "Too many attempts. Try again in 5 minutes."}, status_code=429)
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or not password:
        return JSONResponse({"error": "Username and password required"}, status_code=400)
    conn = _db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row or not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        conn.close()
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), row["id"]))
    conn.commit()
    conn.close()
    _reset_rate_limit(client_ip)
    token = _make_token(row["id"], row["username"], row["role"])
    return {"token": token, "user": {"id": row["id"], "username": row["username"],
            "display_name": row["display_name"], "role": row["role"]}}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = _current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    conn = _db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["user_id"],)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "User not found"}, status_code=404)
    # Get permissions
    perms = _get_all_permissions().get(row["username"], {})
    labels = _get_labels()
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"],
            "role": row["role"], "permissions": perms, "labels": labels, "widget_defaults": WIDGET_DEFAULTS}


@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    conn = _db()
    rows = conn.execute("SELECT id, username, display_name, role, created_at, last_login FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/admin/users")
async def admin_create_user(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    display_name = body.get("display_name", "").strip() or username
    role = body.get("role", "user")
    if not username or not password:
        return JSONResponse({"error": "Username and password required"}, status_code=400)
    if role not in ("admin", "user"):
        role = "user"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = _db()
    try:
        conn.execute("INSERT INTO users (username,password_hash,display_name,role,created_at) VALUES (?,?,?,?,?)",
                     (username, pw_hash, display_name, role, datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse({"error": "Username already exists"}, status_code=409)
    uid = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
    conn.close()
    return {"id": uid, "username": username, "display_name": display_name, "role": role}


@app.put("/api/admin/users/{user_id}")
async def admin_update_user(user_id: int, request: Request):
    body = await request.json()
    conn = _db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "User not found"}, status_code=404)
    updates = []
    params = []
    if "display_name" in body:
        updates.append("display_name = ?")
        params.append(body["display_name"])
    if "role" in body and body["role"] in ("admin", "user"):
        updates.append("role = ?")
        params.append(body["role"])
    if body.get("password"):
        updates.append("password_hash = ?")
        params.append(bcrypt.hashpw(body["password"].encode(), bcrypt.gensalt()).decode())
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    user = _current_user(request)
    if user and user["user_id"] == user_id:
        return JSONResponse({"error": "Cannot delete yourself"}, status_code=400)
    conn = _db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/admin/labels")
async def admin_get_labels(request: Request):
    return {"labels": _get_labels(), "defaults": WIDGET_DEFAULTS}


@app.put("/api/admin/labels")
async def admin_save_labels(request: Request):
    body = await request.json()
    LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LABELS_FILE.write_text(json.dumps(body, indent=2))
    return {"status": "ok"}


@app.get("/api/admin/permissions")
async def admin_get_all_permissions(request: Request):
    return _get_all_permissions()


@app.get("/api/admin/permissions/{username}")
async def admin_get_user_permissions(username: str, request: Request):
    return _get_all_permissions().get(username, {})


@app.put("/api/admin/permissions/{username}")
async def admin_save_user_permissions(username: str, request: Request):
    body = await request.json()
    all_perms = _get_all_permissions()
    all_perms[username] = body
    PERMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PERMISSIONS_FILE.write_text(json.dumps(all_perms, indent=2))
    return {"status": "ok"}

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


# Map dashboard channel numbers to Frigate camera names
# Channel 1 = Front Porch = Frigate "driveway" (misnomed in Frigate)
# Channel 2 = Driveway    = Frigate "rear" (misnomed in Frigate)
CHANNEL_TO_FRIGATE = {1: "driveway", 2: "rear"}

@app.get("/api/cameras/{channel}")
async def camera_snapshot(channel: int):
    """Fetch latest frame from Frigate (fast, cached) with Reolink NVR fallback."""
    frigate_cam = CHANNEL_TO_FRIGATE.get(channel)
    async with httpx.AsyncClient(timeout=5) as client:
        # Primary: Frigate's cached latest frame (no NVR rate-limit issues)
        if frigate_cam:
            try:
                resp = await client.get(f"{FRIGATE_URL}/api/{frigate_cam}/latest.jpg?quality=80")
                if resp.status_code == 200 and len(resp.content) > 1000:
                    return Response(content=resp.content, media_type="image/jpeg",
                                  headers={"Cache-Control": "no-cache"})
            except Exception:
                pass  # Fall through to Reolink
        # Fallback: Reolink NVR direct snapshot
        try:
            url = f"{REOLINK_URL}/cgi-bin/api.cgi?cmd=Snap&channel={channel}&rs=abc123&user={REOLINK_USER}&password={REOLINK_PASS}"
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


# New /api/chat endpoint - replaces the placeholder
@app.post("/api/chat")
async def chat_message(request: Request):
    """Send a message to Alfred via OpenClaw API and get a response"""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return {"error": "Empty message"}
    
    openclaw_url = os.getenv("OPENCLAW_URL", "http://10.10.1.50:18789")
    openclaw_token = os.getenv("OPENCLAW_TOKEN", "")
    
    if not openclaw_token:
        return {"error": "OpenClaw not configured", "response": "I can't connect right now. Message me on Telegram instead."}
    
    # Get or create conversation history
    chat_history_file = Path("/app/data/chat_history.json")
    history = []
    if chat_history_file.exists():
        try:
            history = json.loads(chat_history_file.read_text())
        except:
            history = []
    
    # Keep last 10 messages for context
    history.append({"role": "user", "content": message})
    history = history[-20:]
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                f"{openclaw_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openclaw_token}",
                    "Content-Type": "application/json",
                    "x-openclaw-agent-id": "main",
                },
                json={
                    "model": "openclaw",
                    "user": "batcave-dashboard",
                    "messages": history,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                assistant_msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Filter out NO_REPLY / HEARTBEAT_OK
                if assistant_msg.strip() in ("NO_REPLY", "HEARTBEAT_OK"):
                    assistant_msg = "I'm here. What do you need?"
                
                history.append({"role": "assistant", "content": assistant_msg})
                
                # Save history
                chat_history_file.parent.mkdir(parents=True, exist_ok=True)
                chat_history_file.write_text(json.dumps(history[-20:]))
                
                return {"status": "ok", "response": assistant_msg}
            else:
                return {"error": f"OpenClaw returned {resp.status_code}", "response": "Couldn't reach my brain. Try Telegram."}
        except Exception as e:
            return {"error": str(e), "response": "Connection failed. Try Telegram."}


@app.get("/api/chat/history")
async def chat_history():
    """Get recent chat history"""
    chat_history_file = Path("/app/data/chat_history.json")
    if chat_history_file.exists():
        try:
            return json.loads(chat_history_file.read_text())
        except:
            pass
    return []


@app.get("/api/telegram/recent")
async def telegram_recent():
    """Get recent messages from Telegram (last messages from the bot)"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        return {"error": "Telegram not configured", "messages": []}
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getUpdates",
                params={"offset": -20, "limit": 20}
            )
            if resp.status_code == 200:
                data = resp.json()
                messages = []
                for update in data.get("result", []):
                    msg = update.get("message", {})
                    if str(msg.get("chat", {}).get("id")) == chat_id:
                        messages.append({
                            "text": msg.get("text", ""),
                            "from": msg.get("from", {}).get("first_name", "Unknown"),
                            "is_bot": msg.get("from", {}).get("is_bot", False),
                            "date": msg.get("date", 0),
                        })
                return {"messages": messages[-10:]}
            return {"error": "Telegram API error", "messages": []}
        except Exception as e:
            return {"error": str(e), "messages": []}



# ============================================================
# WebSocket
# ============================================================


# ============================================================
# API Routes — Phase 3: News, Network Topology, Speedtest, Notifications, Timers
# ============================================================

@app.get("/api/news")
async def news_feed(request: Request, keywords: str = None):
    """Curated news ticker — eBPF, federal IT, Cisco, competitors"""
    topics = [
        ("eBPF Cilium cloud native networking", "ebpf"),
        ("federal IT cybersecurity contracts 2026", "federal"),
        ("Cisco Hypershield security", "cisco"),
        ("zero trust microsegmentation federal", "zerotrust"),
    ]
    # Check for custom keywords from user permissions or query param
    if keywords:
        topic_query = keywords
        topic_tag = "custom"
    else:
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
        result = await run_command("speedtest --format=json --accept-license --accept-gdpr 2>/dev/null")
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


# ============================================================
# API Routes — Calendar (ICS feeds + Google Calendar API)
# ============================================================

# Google Calendar API token cache
_google_token_cache = {"access_token": None, "expires_at": 0}

async def _get_google_access_token():
    """Get a valid Google access token, refreshing if needed."""
    import time
    now = time.time()
    if _google_token_cache["access_token"] and _google_token_cache["expires_at"] > now + 60:
        return _google_token_cache["access_token"]
    
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    
    if not all([client_id, client_secret, refresh_token]):
        return None
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        if resp.status_code == 200:
            data = resp.json()
            _google_token_cache["access_token"] = data["access_token"]
            _google_token_cache["expires_at"] = now + data.get("expires_in", 3600)
            return data["access_token"]
    return None

@app.get("/api/calendar")
async def calendar_events(start: str = None, days: int = 30):
    """Fetch and merge events from ICS feeds. start=YYYY-MM-DD, days=window size"""
    from dateutil import tz
    
    eastern = tz.gettz("America/New_York")
    now = datetime.now(tz=eastern)
    if start:
        try:
            today_start = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=eastern)
        except ValueError:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = max(1, min(days, 90))  # clamp 1-90
    window_end = today_start + timedelta(days=days)
    
    all_events = []
    all_sources = []
    
    # --- Part 1: ICS feed sources (AVC calendars etc.) ---
    ics_feeds = [
        {"url": "http://avc13red.woodu2.com/calendar.ics", "source": "AVC 13 Red", "color": "#e83050"},
        {"url": "http://avc15red.woodu2.com/calendar.ics", "source": "AVC 15 Red", "color": "#8860e8"},
        {"url": "https://calendar.google.com/calendar/ical/family12264328603363530032%40group.calendar.google.com/private-1320aa63cd2319afe316b0124cdbeeaa/basic.ics", "source": "Family", "color": "#00e8a0"},
    ]
    
    extra_ics = os.getenv("EXTRA_ICS_FEEDS", "")
    if extra_ics:
        for i, url in enumerate(extra_ics.split(",")):
            url = url.strip()
            if url:
                ics_feeds.append({"url": url, "source": f"Calendar {i+1}", "color": "#00e8d0"})
    
    async with httpx.AsyncClient(timeout=15) as client:
        # Fetch ICS feeds
        for feed in ics_feeds:
            all_sources.append(feed["source"])
            try:
                from icalendar import Calendar as ICalendar
                resp = await client.get(feed["url"])
                if resp.status_code != 200:
                    continue
                
                cal = ICalendar.from_ical(resp.text)
                
                for component in cal.walk():
                    if component.name != "VEVENT":
                        continue
                    
                    summary = str(component.get("SUMMARY", "No Title"))
                    location = str(component.get("LOCATION", "")) if component.get("LOCATION") else ""
                    
                    dtstart = component.get("DTSTART")
                    dtend = component.get("DTEND")
                    
                    if not dtstart:
                        continue
                    
                    start = dtstart.dt
                    end = dtend.dt if dtend else None
                    
                    if hasattr(start, 'hour'):
                        if start.tzinfo is None:
                            start = start.replace(tzinfo=tz.UTC)
                        start = start.astimezone(eastern)
                        if end and hasattr(end, 'hour'):
                            if end.tzinfo is None:
                                end = end.replace(tzinfo=tz.UTC)
                            end = end.astimezone(eastern)
                        all_day = False
                    else:
                        start = datetime.combine(start, datetime.min.time()).replace(tzinfo=eastern)
                        if end:
                            end = datetime.combine(end, datetime.min.time()).replace(tzinfo=eastern)
                        all_day = True
                    
                    if start > window_end or (end and end < today_start) or (not end and start < today_start):
                        continue
                    
                    all_events.append({
                        "title": summary,
                        "start": start.isoformat(),
                        "end": end.isoformat() if end else None,
                        "all_day": all_day,
                        "location": location.replace("\\n", " ").replace("\\,", ",")[:100] if location else "",
                        "source": feed["source"],
                        "color": feed["color"],
                    })
            except Exception as e:
                all_events.append({
                    "title": f"\u26a0 Error loading {feed['source']}",
                    "start": now.isoformat(),
                    "end": None,
                    "all_day": False,
                    "location": str(e)[:80],
                    "source": feed["source"],
                    "color": "#e8a020",
                })
        
        # --- Part 2: Google Calendar API ---
        google_token = await _get_google_access_token()
        if google_token:
            cal_ids_str = os.getenv("GOOGLE_CALENDAR_IDS", "")
            google_calendars = {
                "alfred@saidr.io": {"source": "Alfred", "color": "#00b4e8"},
                # Family calendar now via ICS feed (Part 1)
            }
            
            # Override with env if set
            if cal_ids_str:
                for cid in cal_ids_str.split(","):
                    cid = cid.strip()
                    if cid and cid not in google_calendars:
                        google_calendars[cid] = {"source": cid.split("@")[0][:15], "color": "#00e8d0"}
            
            headers = {"Authorization": f"Bearer {google_token}"}
            time_min = today_start.isoformat()
            time_max = window_end.isoformat()
            
            for cal_id, cal_info in google_calendars.items():
                all_sources.append(cal_info["source"])
                try:
                    import urllib.parse
                    encoded_id = urllib.parse.quote(cal_id)
                    url = (f"https://www.googleapis.com/calendar/v3/calendars/{encoded_id}/events"
                           f"?timeMin={urllib.parse.quote(time_min)}"
                           f"&timeMax={urllib.parse.quote(time_max)}"
                           f"&singleEvents=true&orderBy=startTime&maxResults=100")
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        continue
                    
                    data = resp.json()
                    for item in data.get("items", []):
                        start_info = item.get("start", {})
                        end_info = item.get("end", {})
                        
                        if "dateTime" in start_info:
                            from dateutil.parser import parse as dt_parse
                            start_dt = dt_parse(start_info["dateTime"]).astimezone(eastern)
                            end_dt = dt_parse(end_info["dateTime"]).astimezone(eastern) if "dateTime" in end_info else None
                            all_day = False
                        elif "date" in start_info:
                            start_dt = datetime.strptime(start_info["date"], "%Y-%m-%d").replace(tzinfo=eastern)
                            end_dt = datetime.strptime(end_info["date"], "%Y-%m-%d").replace(tzinfo=eastern) if "date" in end_info else None
                            all_day = True
                        else:
                            continue
                        
                        all_events.append({
                            "title": item.get("summary", "No Title"),
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat() if end_dt else None,
                            "all_day": all_day,
                            "location": (item.get("location", "") or "")[:100],
                            "source": cal_info["source"],
                            "color": cal_info["color"],
                        })
                except Exception as e:
                    all_events.append({
                        "title": f"\u26a0 Error loading {cal_info['source']}",
                        "start": now.isoformat(),
                        "end": None,
                        "all_day": False,
                        "location": str(e)[:80],
                        "source": cal_info["source"],
                        "color": "#e8a020",
                    })
    
    # Sort by start time
    all_events.sort(key=lambda e: e["start"])
    
    # Group by day
    days = {}
    for evt in all_events:
        day_key = evt["start"][:10]
        if day_key not in days:
            days[day_key] = []
        days[day_key].append(evt)
    
    return {"events": all_events, "by_day": days, "sources": all_sources}



@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Auth: require token as query param
    token = ws.query_params.get("token", "")
    user = _decode_token(token) if token else None
    if not user:
        await ws.close(code=4001, reason="Unauthorized")
        return
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
    _init_users_db()
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



# ===== Media Command Center (Plex + Sonarr + Radarr) =====
PLEX_URL = os.getenv("PLEX_URL", "http://10.10.1.5:32400")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
SONARR_URL = os.getenv("SONARR_URL", "http://192.168.11.10:8989")
SONARR_KEY = os.getenv("SONARR_API_KEY", "")
RADARR_URL = os.getenv("RADARR_URL", "http://192.168.11.9:7878")
RADARR_KEY = os.getenv("RADARR_API_KEY", "")


@app.get("/api/plex/recent")
async def plex_recent(count: int = 20):
    """Recently added to Plex"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PLEX_URL}/library/recentlyAdded",
                params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": count},
                headers={"X-Plex-Token": PLEX_TOKEN, "Accept": "application/json"})
            data = r.json()["MediaContainer"].get("Metadata", [])
            return [{"title": m.get("title",""), "year": m.get("year",""),
                     "type": m.get("type",""), "summary": m.get("summary","")[:200],
                     "rating": m.get("audienceRating", m.get("rating","")),
                     "thumb": f"/api/plex/thumb{m['thumb']}" if m.get("thumb") else None,
                     "addedAt": m.get("addedAt",""), "duration": m.get("duration",0),
                     "grandparentTitle": m.get("grandparentTitle",""),
                     "parentTitle": m.get("parentTitle","")} for m in data]
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/plex/search")
async def plex_search(q: str):
    """Search Plex library"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PLEX_URL}/hubs/search",
                params={"query": q, "limit": 20},
                headers={"X-Plex-Token": PLEX_TOKEN, "Accept": "application/json"})
            hubs = r.json()["MediaContainer"].get("Hub", [])
            results = []
            for hub in hubs:
                for m in hub.get("Metadata", []):
                    results.append({"title": m.get("title",""), "year": m.get("year",""),
                                    "type": m.get("type",""), "summary": m.get("summary","")[:200],
                                    "rating": m.get("audienceRating", m.get("rating","")),
                                    "thumb": f"/api/plex/thumb{m['thumb']}" if m.get("thumb") else None})
            return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/plex/thumb/{path:path}")
async def plex_thumb(path: str):
    """Proxy Plex thumbnails"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PLEX_URL}/{path}",
                headers={"X-Plex-Token": PLEX_TOKEN})
            return Response(content=r.content, media_type=r.headers.get("content-type","image/jpeg"))
    except:
        return Response(status_code=404)


@app.get("/api/plex/libraries")
async def plex_libraries():
    """Plex library stats"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PLEX_URL}/library/sections",
                headers={"X-Plex-Token": PLEX_TOKEN, "Accept": "application/json"})
            libs = r.json()["MediaContainer"]["Directory"]
            result = []
            for lib in libs:
                # Get count
                r2 = await c.get(f"{PLEX_URL}/library/sections/{lib['key']}/all?X-Plex-Container-Size=0",
                    headers={"X-Plex-Token": PLEX_TOKEN, "Accept": "application/json"})
                count = r2.json()["MediaContainer"].get("size", r2.json()["MediaContainer"].get("totalSize", 0))
                result.append({"title": lib["title"], "type": lib["type"], "count": count, "key": lib["key"]})
            return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/sonarr/series")
async def sonarr_series():
    """All monitored series from Sonarr"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{SONARR_URL}/api/v3/series",
                headers={"X-Api-Key": SONARR_KEY})
            series = r.json()
            return [{"id": s["id"], "title": s["title"], "year": s.get("year",""),
                     "status": s.get("status",""), "seasons": len(s.get("seasons",[])),
                     "episodeFileCount": s.get("statistics",{}).get("episodeFileCount",0),
                     "totalEpisodeCount": s.get("statistics",{}).get("totalEpisodeCount",0),
                     "sizeOnDisk": s.get("statistics",{}).get("sizeOnDisk",0),
                     "network": s.get("network",""), "overview": s.get("overview","")[:200],
                     "poster": f"/api/sonarr/poster/{s['id']}" if s.get("images") else None,
                     "monitored": s.get("monitored", False)} for s in series]
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/sonarr/poster/{series_id}")
async def sonarr_poster(series_id: int):
    """Proxy Sonarr poster"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{SONARR_URL}/api/v3/series/{series_id}",
                headers={"X-Api-Key": SONARR_KEY})
            images = r.json().get("images", [])
            poster = next((i for i in images if i["coverType"] == "poster"), None)
            if poster and poster.get("remoteUrl"):
                r2 = await c.get(poster["remoteUrl"])
                return Response(content=r2.content, media_type="image/jpeg")
        return Response(status_code=404)
    except:
        return Response(status_code=404)


@app.get("/api/sonarr/search")
async def sonarr_search(q: str):
    """Search for new series to add via Sonarr"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{SONARR_URL}/api/v3/series/lookup",
                params={"term": q}, headers={"X-Api-Key": SONARR_KEY})
            results = r.json()
            # Check which are already added
            r2 = await c.get(f"{SONARR_URL}/api/v3/series",
                headers={"X-Api-Key": SONARR_KEY})
            existing_tvdb = {s.get("tvdbId") for s in r2.json()}
            return [{"title": s.get("title",""), "year": s.get("year",""),
                     "overview": s.get("overview","")[:200], "tvdbId": s.get("tvdbId"),
                     "network": s.get("network",""), "status": s.get("status",""),
                     "seasons": len(s.get("seasons",[])),
                     "rating": s.get("ratings",{}).get("value",""),
                     "poster": next((i["remoteUrl"] for i in s.get("images",[]) if i["coverType"]=="poster"), None),
                     "exists": s.get("tvdbId") in existing_tvdb} for s in results[:15]]
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.post("/api/sonarr/add")
async def sonarr_add(request: Request):
    """Add a series to Sonarr"""
    try:
        body = await request.json()
        tvdb_id = body["tvdbId"]
        async with httpx.AsyncClient(timeout=15) as c:
            # Lookup the series first
            r = await c.get(f"{SONARR_URL}/api/v3/series/lookup",
                params={"term": f"tvdb:{tvdb_id}"}, headers={"X-Api-Key": SONARR_KEY})
            series = r.json()[0]
            # Get root folder
            rf = await c.get(f"{SONARR_URL}/api/v3/rootfolder", headers={"X-Api-Key": SONARR_KEY})
            root = rf.json()[0]["path"]
            # Get quality profile
            qp = await c.get(f"{SONARR_URL}/api/v3/qualityprofile", headers={"X-Api-Key": SONARR_KEY})
            profile_id = qp.json()[0]["id"]
            # Add it
            payload = {**series, "rootFolderPath": root, "qualityProfileId": profile_id,
                       "monitored": True, "addOptions": {"searchForMissingEpisodes": True}}
            r2 = await c.post(f"{SONARR_URL}/api/v3/series",
                json=payload, headers={"X-Api-Key": SONARR_KEY})
            if r2.status_code in (200, 201):
                return {"success": True, "title": series.get("title","")}
            return JSONResponse({"error": r2.text}, r2.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/radarr/movies")
async def radarr_movies():
    """All movies from Radarr"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{RADARR_URL}/api/v3/movie",
                headers={"X-Api-Key": RADARR_KEY})
            movies = r.json()
            return [{"id": m["id"], "title": m["title"], "year": m.get("year",""),
                     "status": m.get("status",""), "hasFile": m.get("hasFile", False),
                     "sizeOnDisk": m.get("sizeOnDisk",0),
                     "overview": m.get("overview","")[:200],
                     "rating": m.get("ratings",{}).get("tmdb",{}).get("value",""),
                     "poster": next((i["remoteUrl"] for i in m.get("images",[]) if i["coverType"]=="poster"), None),
                     "monitored": m.get("monitored", False)} for m in movies]
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/radarr/search")
async def radarr_search(q: str):
    """Search for new movies to add via Radarr"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{RADARR_URL}/api/v3/movie/lookup",
                params={"term": q}, headers={"X-Api-Key": RADARR_KEY})
            results = r.json()
            # Check existing
            r2 = await c.get(f"{RADARR_URL}/api/v3/movie",
                headers={"X-Api-Key": RADARR_KEY})
            existing_tmdb = {m.get("tmdbId") for m in r2.json()}
            return [{"title": m.get("title",""), "year": m.get("year",""),
                     "overview": m.get("overview","")[:200], "tmdbId": m.get("tmdbId"),
                     "runtime": m.get("runtime",0),
                     "rating": m.get("ratings",{}).get("tmdb",{}).get("value",""),
                     "poster": next((i["remoteUrl"] for i in m.get("images",[]) if i["coverType"]=="poster"), None),
                     "exists": m.get("tmdbId") in existing_tmdb} for m in results[:15]]
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.post("/api/radarr/add")
async def radarr_add(request: Request):
    """Add a movie to Radarr"""
    try:
        body = await request.json()
        tmdb_id = body["tmdbId"]
        async with httpx.AsyncClient(timeout=15) as c:
            # Lookup
            r = await c.get(f"{RADARR_URL}/api/v3/movie/lookup",
                params={"term": f"tmdb:{tmdb_id}"}, headers={"X-Api-Key": RADARR_KEY})
            movie = r.json()[0]
            # Root folder
            rf = await c.get(f"{RADARR_URL}/api/v3/rootfolder", headers={"X-Api-Key": RADARR_KEY})
            root = rf.json()[0]["path"]
            # Quality profile
            qp = await c.get(f"{RADARR_URL}/api/v3/qualityprofile", headers={"X-Api-Key": RADARR_KEY})
            profile_id = qp.json()[0]["id"]
            # Add
            payload = {**movie, "rootFolderPath": root, "qualityProfileId": profile_id,
                       "monitored": True, "addOptions": {"searchForMovie": True}}
            r2 = await c.post(f"{RADARR_URL}/api/v3/movie",
                json=payload, headers={"X-Api-Key": RADARR_KEY})
            if r2.status_code in (200, 201):
                return {"success": True, "title": movie.get("title","")}
            return JSONResponse({"error": r2.text}, r2.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/media/recommendations")
async def media_recommendations():
    """AI recommendations based on library analysis"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            # Get recent Plex watches for context
            r = await c.get(f"{PLEX_URL}/library/recentlyAdded",
                params={"X-Plex-Container-Size": 30},
                headers={"X-Plex-Token": PLEX_TOKEN, "Accept": "application/json"})
            recent = r.json()["MediaContainer"].get("Metadata", [])
            recent_titles = [f"{m.get('title','')} ({m.get('year','')})" for m in recent[:15]]

            # Get Sonarr series for taste profile
            r2 = await c.get(f"{SONARR_URL}/api/v3/series",
                headers={"X-Api-Key": SONARR_KEY})
            series = r2.json()
            series_titles = [s["title"] for s in sorted(series, key=lambda x: x.get("statistics",{}).get("episodeFileCount",0), reverse=True)[:20]]

            # Use OpenClaw/Alfred for recommendations
            openclaw_url = os.getenv("OPENCLAW_URL", "")
            openclaw_token = os.getenv("OPENCLAW_TOKEN", "")
            if not openclaw_url or not openclaw_token:
                return {"movies": [], "shows": [], "error": "OpenClaw not configured"}

            prompt = f"""Based on this family's media library, suggest 5 movies and 5 TV shows they'd enjoy but DON'T already have. 
            
Family profile: Dad (tech guy, likes Batman/action/sci-fi), Mom, two daughters (teens).

Recently added movies/shows: {', '.join(recent_titles)}
Favorite TV series (most episodes): {', '.join(series_titles)}

Return ONLY valid JSON with this format, no other text:
{{"movies": [{{"title": "...", "year": 2024, "why": "one sentence reason"}}], "shows": [{{"title": "...", "year": 2024, "why": "one sentence reason"}}]}}"""

            r3 = await c.post(f"{openclaw_url}/v1/chat/completions",
                json={"model": "default", "messages": [{"role": "user", "content": prompt}], "temperature": 0.8},
                headers={"Authorization": f"Bearer {openclaw_token}"}, timeout=30)
            content = r3.json()["choices"][0]["message"]["content"]
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"movies": [], "shows": [], "raw": content}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


# ============================================================
# ADT SECURITY / ALARM.COM INTEGRATION
# ============================================================

@app.get("/api/security/status")
async def security_status():
    """Get full ADT security system status from HA entities."""
    if not HA_TOKEN:
        return {"error": "HA not configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{HA_URL}/api/states", headers=HA_HEADERS)
            states = resp.json()

        # Build a lookup
        state_map = {s["entity_id"]: s for s in states}

        # Alarm panel
        panel = state_map.get("alarm_control_panel.panel", {})
        alarm = {
            "state": panel.get("state", "unknown"),
            "friendly_name": panel.get("attributes", {}).get("friendly_name", "Panel"),
        }

        # Locks
        locks = []
        for eid in ["lock.front_door_lock", "lock.back_door_lock", "lock.patio_door_lock"]:
            s = state_map.get(eid, {})
            attrs = s.get("attributes", {})
            locks.append({
                "entity_id": eid,
                "name": attrs.get("friendly_name", eid.split(".")[-1].replace("_", " ").title()),
                "state": s.get("state", "unknown"),
            })

        # Garage doors
        garages = []
        for eid in ["cover.big_garage", "cover.lil_garage"]:
            s = state_map.get(eid, {})
            attrs = s.get("attributes", {})
            garages.append({
                "entity_id": eid,
                "name": attrs.get("friendly_name", eid.split(".")[-1].replace("_", " ").title()),
                "state": s.get("state", "unknown"),
            })

        # Thermostats
        thermostats = []
        for eid in ["climate.thermostat_main_floor", "climate.thermostat_bathroom",
                     "climate.thermostat_master_bedroom", "climate.thermostat_girls_bedrooms"]:
            s = state_map.get(eid, {})
            attrs = s.get("attributes", {})
            thermostats.append({
                "entity_id": eid,
                "name": attrs.get("friendly_name", eid.split(".")[-1].replace("_", " ").title()),
                "state": s.get("state", "unknown"),
                "current_temp": attrs.get("current_temperature"),
                "target_temp": attrs.get("temperature"),
                "hvac_action": attrs.get("hvac_action", ""),
                "hvac_modes": attrs.get("hvac_modes", []),
                "min_temp": attrs.get("min_temp", 45),
                "max_temp": attrs.get("max_temp", 95),
            })

        # Door/window sensors
        sensors = []
        sensor_ids = [
            "binary_sensor.front_door", "binary_sensor.back_door",
            "binary_sensor.bsmt_door",
            "binary_sensor.garage_door_1", "binary_sensor.garage_door_2",
            "binary_sensor.back_win_1", "binary_sensor.back_win_2",
            "binary_sensor.bsmt_win_1", "binary_sensor.bsmt_win_2", "binary_sensor.bsmt_win_3",
            "binary_sensor.dining_rm_win_1", "binary_sensor.dining_rm_win_2",
            "binary_sensor.fam_rm_win_1", "binary_sensor.fam_rm_win_2",
            "binary_sensor.ofc_win_1", "binary_sensor.ofc_win_2",
            "binary_sensor.ofc_win_3", "binary_sensor.ofc_win_4",
            "binary_sensor.gb_front", "binary_sensor.gb_ofc",
            "binary_sensor.mt_det_bsmt",
        ]
        open_count = 0
        for eid in sensor_ids:
            s = state_map.get(eid, {})
            attrs = s.get("attributes", {})
            st = s.get("state", "unknown")
            if st == "on":
                open_count += 1
            sensors.append({
                "entity_id": eid,
                "name": attrs.get("friendly_name", eid.split(".")[-1].replace("_", " ").title()),
                "state": st,
            })

        # Lights (ADT-controlled)
        lights = []
        for eid in ["light.office_tree", "light.light_plug", "light.living_room_tree"]:
            s = state_map.get(eid, {})
            attrs = s.get("attributes", {})
            lights.append({
                "entity_id": eid,
                "name": attrs.get("friendly_name", eid.split(".")[-1].replace("_", " ").title()),
                "state": s.get("state", "unknown"),
            })

        return {
            "alarm": alarm,
            "locks": locks,
            "garages": garages,
            "thermostats": thermostats,
            "sensors": sensors,
            "lights": lights,
            "open_sensors": open_count,
            "total_sensors": len(sensor_ids),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/security/lock/{action}")
async def security_lock_action(action: str, request: Request):
    """Lock/unlock a door."""
    if not HA_TOKEN:
        return {"error": "HA not configured"}
    data = await request.json()
    entity_id = data.get("entity_id", "")
    if not entity_id.startswith("lock."):
        return {"error": "Invalid entity"}
    service = f"lock/{action}"  # lock/lock or lock/unlock
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{HA_URL}/api/services/{service}",
                                     headers=HA_HEADERS,
                                     json={"entity_id": entity_id})
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/security/alarm/{action}")
async def security_alarm_action(action: str):
    """Arm/disarm the alarm. Actions: arm_away, arm_home, arm_night, disarm"""
    if not HA_TOKEN:
        return {"error": "HA not configured"}
    service = f"alarm_control_panel/alarm_{action}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{HA_URL}/api/services/{service}",
                                     headers=HA_HEADERS,
                                     json={"entity_id": "alarm_control_panel.panel"})
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/security/garage/{action}")
async def security_garage_action(action: str, request: Request):
    """Open/close garage door."""
    if not HA_TOKEN:
        return {"error": "HA not configured"}
    data = await request.json()
    entity_id = data.get("entity_id", "")
    if not entity_id.startswith("cover."):
        return {"error": "Invalid entity"}
    service = f"cover/{action}_cover"  # cover/open_cover or cover/close_cover
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{HA_URL}/api/services/{service}",
                                     headers=HA_HEADERS,
                                     json={"entity_id": entity_id})
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}



@app.post("/api/security/climate/set_temp")
async def climate_set_temp(request: Request):
    """Set thermostat target temperature."""
    if not HA_TOKEN:
        return {"error": "HA not configured"}
    data = await request.json()
    entity_id = data.get("entity_id", "")
    temperature = data.get("temperature")
    if not entity_id.startswith("climate.") or temperature is None:
        return {"error": "Invalid params"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{HA_URL}/api/services/climate/set_temperature",
                                     headers=HA_HEADERS,
                                     json={"entity_id": entity_id, "temperature": float(temperature)})
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/security/climate/set_mode")
async def climate_set_mode(request: Request):
    """Set thermostat HVAC mode (heat, cool, heat_cool, off)."""
    if not HA_TOKEN:
        return {"error": "HA not configured"}
    data = await request.json()
    entity_id = data.get("entity_id", "")
    hvac_mode = data.get("hvac_mode", "")
    if not entity_id.startswith("climate.") or not hvac_mode:
        return {"error": "Invalid params"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{HA_URL}/api/services/climate/set_hvac_mode",
                                     headers=HA_HEADERS,
                                     json={"entity_id": entity_id, "hvac_mode": hvac_mode})
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}

# --- Static files (mount LAST) ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")
