from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime, date, timedelta
import re
import os
from .auth import hash_password, verify_password

DB = os.path.join(os.path.dirname(__file__), "habit_tracker.db")

app = Flask(__name__)
# allow your React dev server to call this API
CORS(app, origins=["http://localhost:3000"], supports_credentials=True)

def get_user_by_email(email: str):
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, first_name, last_name, username, email, password_hash
            FROM users WHERE email = ? LIMIT 1
        """, (email,))
        return cur.fetchone()

@app.post("/api/signup")
def signup():
    data = request.get_json(force=True)
    required = ["first_name","last_name","username","email","password"]
    if any(not data.get(k) for k in required):
        return jsonify({"error":"Missing fields"}), 400

    # email unique?
    if get_user_by_email(data["email"]):
        return jsonify({"error":"Email already in use"}), 409

    pw_hash = hash_password(data["password"])
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (first_name,last_name,username,email,password_hash)
                VALUES (?,?,?,?,?)
            """, (data["first_name"], data["last_name"], data["username"], data["email"], pw_hash))
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"error":"Username already in use"}), 409

    return jsonify({"user_id": user_id}), 201

@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    row = get_user_by_email(email)
    if not row:
        return jsonify({"error":"Invalid credentials"}), 401

    user_id, first, last, username, email, pw_hash = row
    if not verify_password(password, pw_hash):
        return jsonify({"error":"Invalid credentials"}), 401

    # For demo: return a fake token (later: set httpOnly cookie)
    return jsonify({
        "token":"demo-token",
        "user":{
            "user_id": user_id,
            "first_name": first,
            "last_name": last,
            "username": username,
            "email": email
        }
    }), 200
def _user_exists(user_id:int) -> bool:
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE user_id=? LIMIT 1", (user_id,))
        return cur.fetchone() is not None

def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday

@app.get("/api/habits")
def list_habits():
    """
    GET /api/habits?user_id=1&preset=today|this_week
    or /api/habits?user_id=1&start=YYYY-MM-DD&end=YYYY-MM-DD
    """
    user_id = request.args.get("user_id", type=int)
    preset  = request.args.get("preset", type=str)
    start   = request.args.get("start", type=str)
    end     = request.args.get("end", type=str)

    if not user_id:
        return jsonify({"error":"user_id is required"}), 400
    if not _user_exists(user_id):
        return jsonify({"error":"user not found"}), 404

    where = ["user_id = ?"]
    params = [user_id]

    today = date.today()
    if preset == "today":
        where.append("DATE(timestamp) = ?")
        params.append(today.isoformat())
    elif preset == "this_week":
        ws = _week_start(today).isoformat()
        where.append("DATE(timestamp) BETWEEN ? AND ?")
        params.extend([ws, today.isoformat()])
    elif start or end:
        if not (start and end):
            return jsonify({"error":"start and end are required together (YYYY-MM-DD)"}), 400
        # minimal validation
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error":"dates must be YYYY-MM-DD"}), 400
        where.append("DATE(timestamp) BETWEEN ? AND ?")
        params.extend([start, end])

    sql = f"""
      SELECT habit_id, habit_name, duration, COALESCE(duration_minutes, NULL) AS duration_minutes, timestamp
      FROM habits
      WHERE {' AND '.join(where)}
      ORDER BY timestamp DESC, habit_id DESC
    """
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    habits = [
        {
          "habit_id": r[0],
          "habit_name": r[1],
          "duration": r[2],
          "duration_minutes": r[3],
          "timestamp": r[4],
        } for r in rows
    ]
    return jsonify({"habits": habits})

# --- Minimal duration parser (accepts '30 min', '1 hour', '90', '1:30') ---
_min_pat = re.compile(r"^\s*(\d+)\s*(min|mins?|minute|minutes)?\s*$", re.I)
_hr_pat  = re.compile(r"^\s*(\d+)\s*(h|hr|hrs|hour|hours)\s*$", re.I)
_hm_pat  = re.compile(r"^\s*(\d+)\s*:\s*(\d+)\s*$")

def _to_minutes(text: str) -> int:
    t = text.strip()
    m = _hm_pat.match(t)
    if m: return int(m.group(1))*60 + int(m.group(2))
    m = _hr_pat.match(t)
    if m: return int(m.group(1))*60
    m = _min_pat.match(t)
    if m: return int(m.group(1))
    raise ValueError("Unrecognized duration format (try '30 min', '1 hour', '1:30', or plain minutes)")

@app.post("/api/habits")
def add_habit():
    """
    POST /api/habits
    { "user_id": 1, "habit_name": "Read", "duration": "30 min", "timestamp": "optional ISO-8601" }
    """
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    habit_name = (data.get("habit_name") or "").strip()
    duration_text = (data.get("duration") or "").strip()
    timestamp_iso = data.get("timestamp")

    if not user_id or not _user_exists(user_id):
        return jsonify({"error":"valid user_id is required"}), 400
    if not habit_name:
        return jsonify({"error":"habit_name is required"}), 400
    if not duration_text:
        return jsonify({"error":"duration is required"}), 400

    try:
        minutes = _to_minutes(duration_text)
        if minutes <= 0:
            return jsonify({"error":"duration must be > 0"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        if timestamp_iso:
            # validate timestamp a bit
            try:
                datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            except Exception:
                return jsonify({"error":"timestamp must be ISO-8601 like 2025-11-06T14:30:00"}), 400
            cur.execute("""
              INSERT INTO habits (user_id, habit_name, duration, duration_minutes, timestamp)
              VALUES (?, ?, ?, ?, ?)
            """, (user_id, habit_name, duration_text, minutes, timestamp_iso))
        else:
            cur.execute("""
              INSERT INTO habits (user_id, habit_name, duration, duration_minutes)
              VALUES (?, ?, ?, ?)
            """, (user_id, habit_name, duration_text, minutes))
        habit_id = cur.lastrowid
        conn.commit()

    return jsonify({"habit_id": habit_id}), 201

@app.put("/api/habits/<int:habit_id>")
def update_habit(habit_id: int):
    """
    PUT /api/habits/123
    { "user_id": 1, "habit_name": "Read", "duration": "45 min" }
    duration is optional but if provided will be re-parsed to minutes.
    """
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    if not user_id or not _user_exists(user_id):
        return jsonify({"error": "valid user_id is required"}), 400

    habit_name = data.get("habit_name")
    duration_text = data.get("duration")

    sets = []
    params = []

    if habit_name is not None:
        hn = habit_name.strip()
        if not hn:
            return jsonify({"error": "habit_name cannot be empty"}), 400
        sets.append("habit_name = ?")
        params.append(hn)

    if duration_text is not None:
        dt = duration_text.strip()
        if not dt:
            return jsonify({"error": "duration cannot be empty"}), 400
        try:
            minutes = _to_minutes(dt)
            if minutes <= 0:
                return jsonify({"error": "duration must be > 0"}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        sets.append("duration = ?")
        params.append(dt)
        sets.append("duration_minutes = ?")
        params.append(minutes)

    if not sets:
        return jsonify({"error": "nothing to update"}), 400

    # Only update if the habit belongs to the user
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE habits SET {', '.join(sets)} WHERE habit_id = ? AND user_id = ?",
            (*params, habit_id, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "habit not found for this user"}), 404
        conn.commit()

    return jsonify({"updated": True})

@app.delete("/api/habits/<int:habit_id>")
def delete_habit(habit_id: int):
    """
    DELETE /api/habits/123?user_id=1
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id or not _user_exists(user_id):
        return jsonify({"error": "valid user_id is required"}), 400

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM habits WHERE habit_id = ? AND user_id = ?",
                    (habit_id, user_id))
        if cur.rowcount == 0:
            return jsonify({"error": "habit not found for this user"}), 404
        conn.commit()
    return jsonify({"deleted": True})
@app.get("/api/summary/weekly")
def weekly_summary():
    """
    GET /api/summary/weekly?user_id=1
    Returns totals per day (Mon..Sun) for the current week and a weekly total.
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id or not _user_exists(user_id):
        return jsonify({"error":"valid user_id is required"}), 400

    today = date.today()
    start = _week_start(today).isoformat()
    end = today.isoformat()

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT DATE(timestamp) AS d, COALESCE(SUM(duration_minutes), 0)
        FROM habits
        WHERE user_id = ? AND DATE(timestamp) BETWEEN ? AND ?
        GROUP BY DATE(timestamp)
        """, (user_id, start, end))
        rows = cur.fetchall()

    # Build a dict of day->minutes for the week
    totals = {}
    for i in range(7):
        day = (_week_start(today) + timedelta(days=i)).isoformat()
        totals[day] = 0
    for d, s in rows:
        if d in totals:
            totals[d] = int(s or 0)

    weekly_total = sum(totals.values())
    return jsonify({"start_of_week": start, "today": end, "per_day": totals, "weekly_total_minutes": weekly_total})

@app.get("/api/summary/streak")
def streak_summary():
    """
    GET /api/summary/streak?user_id=1
    A 'streak day' = a date with >= 1 habit. Computes current streak ending today, and longest historical streak.
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id or not _user_exists(user_id):
        return jsonify({"error":"valid user_id is required"}), 400

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT DATE(timestamp), COUNT(*)
        FROM habits
        WHERE user_id = ?
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp)
        """, (user_id,))
        rows = cur.fetchall()

    # Convert to sorted list of dates with activity
    active_days = [date.fromisoformat(r[0]) for r in rows]

    # Longest streak
    longest = 0
    cur_len = 0
    prev = None
    for d in active_days:
        if prev is None or (d - prev).days == 1:
            cur_len += 1
        else:
            longest = max(longest, cur_len)
            cur_len = 1
        prev = d
    longest = max(longest, cur_len)

    # Current streak (must end today)
    today = date.today()
    current = 0
    day_check = today
    active_set = set(active_days)
    while day_check in active_set:
        current += 1
        day_check = day_check - timedelta(days=1)

    return jsonify({"current_streak_days": current, "longest_streak_days": longest})

@app.route("/api/friends", methods=["POST"])
def add_friend():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    friend_email = data.get("friend_email")

    if not user_id or not friend_email:
        return jsonify({"error": "user_id and friend_email are required"}), 400

    # ensure user exists
    if not _user_exists(int(user_id)):
        return jsonify({"error": "user not found"}), 404

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()

        # Look up friend by email
        cur.execute("SELECT user_id FROM users WHERE email = ?", (friend_email,))
        row = cur.fetchone()

        if not row:
            return jsonify({"error": "No user found with that email"}), 404

        friend_id = row[0]

        # Cannot add yourself
        if int(user_id) == int(friend_id):
            return jsonify({"error": "You cannot add yourself as a friend"}), 400

        try:
            cur.execute("""
                INSERT INTO friends (user_id, friend_id)
                VALUES (?, ?)
            """, (user_id, friend_id))
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "You already added this friend"}), 400

    return jsonify({"message": "Friend added successfully"}), 201


@app.route("/api/friends", methods=["GET"])
def list_friends():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    if not _user_exists(user_id):
        return jsonify({"error": "user not found"}), 404

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.user_id, u.username, u.email
            FROM friends f
            JOIN users u ON f.friend_id = u.user_id
            WHERE f.user_id = ?
            ORDER BY u.username
        """, (user_id,))

        friends = [
            {"user_id": row[0], "username": row[1], "email": row[2]}
            for row in cur.fetchall()
        ]

    return jsonify({"friends": friends})

if __name__ == "__main__":
    # Use a fixed port so React (3000) can call us at 5000
    app.run(host="127.0.0.1", port=5000, debug=True)