import React, { useEffect, useMemo, useState, useCallback } from "react";

export default function Dashboard({ auth, onLogout }) {
  const user = auth?.user;
  const API = "http://127.0.0.1:5000";

  const [habits, setHabits] = useState([]);
  const [filter, setFilter] = useState("this_week"); // "", "today", "this_week"
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Add form
  const [name, setName] = useState("");
  const [duration, setDuration] = useState("");

  // Edit state
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editDuration, setEditDuration] = useState("");

  // Summary of habits
  const [weeklyTotal, setWeeklyTotal] = useState(0);
  const [currentStreak, setCurrentStreak] = useState(0);
  const [longestStreak, setLongestStreak] = useState(0);

  // Add friends
  const [friends, setFriends] = useState([]);
  const [friendEmail, setFriendEmail] = useState("");
  const [friendMessage, setFriendMessage] = useState("");

  const displayName = useMemo(() => {
    if (!user) return "";
    if (user.first_name || user.last_name)
      return `${user.first_name || ""} ${user.last_name || ""}`.trim();
    return user.username || user.email;
  }, [user]);

  const loadHabits = useCallback(async () => {
    if (!user?.user_id) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ user_id: String(user.user_id) });
      if (filter === "today" || filter === "this_week") params.set("preset", filter);
      const res = await fetch(`${API}/api/habits?` + params.toString());
      if (!res.ok) throw new Error("Failed to fetch habits");
      const data = await res.json();
      setHabits(data.habits || []);
    } catch (e) {
      setError(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [API, filter, user?.user_id]);

  const loadWeeklyTotal = useCallback(async () => {
    if (!user?.user_id) return;
    try {
      const res = await fetch(`${API}/api/summary/weekly?user_id=${user.user_id}`);
      if (!res.ok) return;
      const data = await res.json();
      setWeeklyTotal(data.weekly_total_minutes || 0);
    } catch {}
  }, [API, user?.user_id]);

  const loadStreaks = useCallback(async () => {
    if (!user?.user_id) return;
    try {
      const res = await fetch(`${API}/api/summary/streak?user_id=${user.user_id}`);
      if (!res.ok) return;
      const data = await res.json();
      setCurrentStreak(data.current_streak_days || 0);
      setLongestStreak(data.longest_streak_days || 0);
    } catch {}
  }, [API, user?.user_id]);

  // Load friends for this user
  const loadFriends = useCallback(async () => {
    if (!user?.user_id) return;
    try {
      const res = await fetch(`${API}/api/friends?user_id=${user.user_id}`);
      if (!res.ok) return;
      const data = await res.json();
      setFriends(data.friends || []);
    } catch {}
  }, [API, user?.user_id]);

  // Load habits when filter/user changes
  useEffect(() => {
    loadHabits();
  }, [loadHabits]);

  // Load summaries when habits change
  useEffect(() => {
    loadWeeklyTotal();
    loadStreaks();
  }, [loadWeeklyTotal, loadStreaks, habits.length]);

  // Load friends on mount / when user changes
  useEffect(() => {
    loadFriends();
  }, [loadFriends]);

  const handleAddFriend = async (e) => {
    e.preventDefault();
    if (!auth?.user) return;

    setFriendMessage("");

    const res = await fetch(`${API}/api/friends`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: auth.user.user_id,
        friend_email: friendEmail,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      setFriendMessage(data.error || "Failed to add friend");
    } else {
      setFriendMessage("Friend added!");
      setFriendEmail("");
      loadFriends(); // refresh list
    }
  };

  async function addHabit(e) {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !duration.trim()) {
      setError("Please enter habit name and duration");
      return;
    }
    const res = await fetch(`${API}/api/habits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: user.user_id,
        habit_name: name.trim(),
        duration: duration.trim(),
      }),
    });
    const data = await res.json().catch(() => ({ error: "Failed" }));
    if (!res.ok) return setError(data.error || "Failed to add habit");
    setName("");
    setDuration("");
    await loadHabits();
    await loadWeeklyTotal();
    await loadStreaks();
  }

  function startEdit(h) {
    setEditingId(h.habit_id);
    setEditName(h.habit_name);
    setEditDuration(h.duration);
  }

  async function saveEdit(habit_id) {
    if (!editName.trim() || !editDuration.trim()) {
      setError("Name and duration are required");
      return;
    }
    const res = await fetch(`${API}/api/habits/${habit_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: user.user_id,
        habit_name: editName.trim(),
        duration: editDuration.trim(),
      }),
    });
    const data = await res.json().catch(() => ({ error: "Failed" }));
    if (!res.ok) return setError(data.error || "Failed to update habit");
    setEditingId(null);
    await loadHabits();
    await loadWeeklyTotal();
    await loadStreaks();
  }

  async function deleteHabit(habit_id) {
    if (!window.confirm("Delete this habit?")) return;
    const res = await fetch(
      `${API}/api/habits/${habit_id}?user_id=${user.user_id}`,
      { method: "DELETE" }
    );
    const data = await res.json().catch(() => ({ error: "Failed" }));
    if (!res.ok) return setError(data.error || "Failed to delete habit");
    await loadHabits();
    await loadWeeklyTotal();
    await loadStreaks();
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900">
            Hi, {displayName || "there"} 👋
          </h1>
          <button
            onClick={onLogout}
            className="text-sm rounded-xl px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800"
          >
            Log out
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Summary cards */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-4">
            <div className="text-sm text-slate-500">Weekly total</div>
            <div className="text-2xl font-semibold text-slate-900">
              {weeklyTotal} min
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-4">
            <div className="text-sm text-slate-500">Current streak</div>
            <div className="text-2xl font-semibold text-slate-900">
              {currentStreak} day{currentStreak === 1 ? "" : "s"}
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-4">
            <div className="text-sm text-slate-500">Longest streak</div>
            <div className="text-2xl font-semibold text-slate-900">
              {longestStreak} day{longestStreak === 1 ? "" : "s"}
            </div>
          </div>
        </section>

        {/* Add habit */}
        <section>
          <form
            onSubmit={addHabit}
            className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-col sm:flex-row gap-3"
          >
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 rounded-xl border border-slate-300 px-3 py-2 outline-none"
              placeholder="Habit name (e.g., Read)"
            />
            <input
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              className="w-full sm:w-48 rounded-xl border border-slate-300 px-3 py-2 outline-none"
              placeholder="Duration (e.g., 30 min, 1:30)"
            />
            <button className="rounded-xl px-4 py-2 bg-slate-900 text-white hover:bg-slate-800">
              Add habit
            </button>
          </form>
        </section>

        {/* Filters + table */}
        <section className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Your habits</h2>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-xl border border-slate-300 px-3 py-2 bg-white"
          >
            <option value="">All time</option>
            <option value="today">Today</option>
            <option value="this_week">This week</option>
          </select>
        </section>

        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl p-2">
            {error}
          </div>
        )}

        <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          <div className="grid grid-cols-12 px-4 py-2 text-xs font-semibold text-slate-500 border-b border-slate-200">
            <div className="col-span-4 sm:col-span-4">Habit</div>
            <div className="col-span-2 sm:col-span-2">Duration</div>
            <div className="col-span-3 sm:col-span-3">Timestamp</div>
            <div className="hidden sm:block sm:col-span-2">Minutes</div>
            <div className="col-span-3 sm:col-span-1 text-right">Actions</div>
          </div>

          {loading ? (
            <div className="p-4 text-slate-600">Loading…</div>
          ) : habits.length === 0 ? (
            <div className="p-4 text-slate-600">No habits yet.</div>
          ) : (
            habits.map((h) => (
              <div
                key={h.habit_id}
                className="grid grid-cols-12 px-4 py-2 border-b last:border-b-0 border-slate-100 text-sm items-center"
              >
                <div className="col-span-4 sm:col-span-4">
                  {editingId === h.habit_id ? (
                    <input
                      className="w-full rounded-xl border border-slate-300 px-2 py-1"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                    />
                  ) : (
                    h.habit_name
                  )}
                </div>
                <div className="col-span-2 sm:col-span-2">
                  {editingId === h.habit_id ? (
                    <input
                      className="w-full rounded-xl border border-slate-300 px-2 py-1"
                      value={editDuration}
                      onChange={(e) => setEditDuration(e.target.value)}
                    />
                  ) : (
                    h.duration
                  )}
                </div>
                <div className="col-span-3 sm:col-span-3">
                  {h.timestamp?.replace("T", " ").slice(0, 16)}
                </div>
                <div className="hidden sm:block sm:col-span-2">
                  {h.duration_minutes ?? "—"}
                </div>
                <div className="col-span-3 sm:col-span-1 flex justify-end gap-2">
                  {editingId === h.habit_id ? (
                    <>
                      <button
                        className="text-xs rounded-lg px-2 py-1 bg-emerald-600 text-white"
                        onClick={() => saveEdit(h.habit_id)}
                      >
                        Save
                      </button>
                      <button
                        className="text-xs rounded-lg px-2 py-1 bg-slate-200"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        className="text-xs rounded-lg px-2 py-1 bg-slate-200"
                        onClick={() => startEdit(h)}
                      >
                        Edit
                      </button>
                      <button
                        className="text-xs rounded-lg px-2 py-1 bg-red-600 text-white"
                        onClick={() => deleteHabit(h.habit_id)}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </section>

        {/* Friends section */}
        <section>
          <div className="bg-white border border-slate-200 rounded-2xl p-4 max-w-md">
            <h2 className="text-lg font-semibold mb-2 text-slate-900">
              Add a Friend
            </h2>

            <form onSubmit={handleAddFriend} className="space-y-2">
              <input
                type="email"
                value={friendEmail}
                onChange={(e) => setFriendEmail(e.target.value)}
                placeholder="Friend's email"
                className="w-full border rounded-xl px-3 py-2 text-sm border-slate-300 outline-none"
                required
              />
              <button
                type="submit"
                className="px-4 py-2 text-sm font-medium rounded-xl bg-blue-600 text-white hover:bg-blue-500"
              >
                Add Friend
              </button>
            </form>

            {friendMessage && (
              <p className="mt-2 text-sm text-slate-700">{friendMessage}</p>
            )}

            <h3 className="text-md font-semibold mt-4 text-slate-900">
              Your Friends
            </h3>
            <ul className="mt-1 text-sm list-disc list-inside text-slate-700">
              {friends.length === 0 && <li>No friends yet.</li>}
              {friends.map((f) => (
                <li key={f.user_id}>
                  {f.username} ({f.email})
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
}