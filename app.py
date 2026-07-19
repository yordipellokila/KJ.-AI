"""
KJ-AI Backend — mengatur proses pendataan (data collection) untuk web skrining
kesehatan jiwa mahasiswa.

Fungsi utama:
- Menyajikan halaman kj.html
- Menerima & menyimpan hasil asesmen ke database SQLite (bukan cuma localStorage)
- Menyediakan riwayat per-mahasiswa (berdasarkan NIM)
- Menyediakan data rekap untuk dashboard admin
- Verifikasi passcode admin di sisi server

Cara menjalankan:
    pip install -r requirements.txt
    python app.py
Lalu buka http://localhost:5000
"""

import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kj_data.db")

# Ganti passcode ini sesuai kebutuhan, atau set lewat environment variable
ADMIN_PASSCODE = os.environ.get("KJ_ADMIN_PASSCODE", "KJADMIN123")

app = Flask(__name__, static_folder=BASE_DIR)


# ---------- Koneksi Database ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            raw_date TEXT NOT NULL,
            student_name TEXT NOT NULL,
            student_nim TEXT NOT NULL,
            score INTEGER NOT NULL,
            risk TEXT NOT NULL,
            bayes_result TEXT,
            breakdown TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# ---------- Halaman Web ----------

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "kj.html")


# ---------- API: Autentikasi Admin ----------

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if code == ADMIN_PASSCODE:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Passcode salah"}), 401


# ---------- API: Simpan Hasil Asesmen ----------

@app.route("/api/records", methods=["POST"])
def create_record():
    data = request.get_json(silent=True) or {}

    required = ["studentName", "studentNim", "score", "risk"]
    missing = [f for f in required if not data.get(f) and data.get(f) != 0]
    if missing:
        return jsonify({"ok": False, "message": f"Field wajib kosong: {', '.join(missing)}"}), 400

    record_id = data.get("id") or f"REC-{int(datetime.now().timestamp() * 1000)}"
    raw_date = data.get("rawDate") or datetime.now().isoformat()
    date_display = data.get("date") or datetime.now().strftime("%d %b %Y")

    db = get_db()
    db.execute(
        """
        INSERT INTO records (id, date, raw_date, student_name, student_nim,
                              score, risk, bayes_result, breakdown, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            date_display,
            raw_date,
            data["studentName"],
            data["studentNim"],
            int(data["score"]),
            data["risk"],
            data.get("bayesResult", ""),
            json.dumps(data.get("breakdown", [])),
            datetime.now().isoformat(),
        ),
    )
    db.commit()

    return jsonify({"ok": True, "id": record_id})


def row_to_dict(row):
    return {
        "id": row["id"],
        "date": row["date"],
        "rawDate": row["raw_date"],
        "studentName": row["student_name"],
        "studentNim": row["student_nim"],
        "score": row["score"],
        "risk": row["risk"],
        "bayesResult": row["bayes_result"],
        "breakdown": json.loads(row["breakdown"] or "[]"),
    }


# ---------- API: Riwayat Mahasiswa (per NIM) ----------

@app.route("/api/records/student/<nim>", methods=["GET"])
def get_student_records(nim):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM records WHERE student_nim = ? ORDER BY raw_date ASC",
        (nim,),
    ).fetchall()
    return jsonify({"ok": True, "records": [row_to_dict(r) for r in rows]})


# ---------- API: Semua Data (Dashboard Admin) ----------

@app.route("/api/records", methods=["GET"])
def get_all_records():
    query = request.args.get("q", "").lower().strip()
    db = get_db()

    if query:
        like = f"%{query}%"
        rows = db.execute(
            """
            SELECT * FROM records
            WHERE lower(student_name) LIKE ? OR lower(student_nim) LIKE ?
            ORDER BY raw_date DESC
            """,
            (like, like),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM records ORDER BY raw_date DESC").fetchall()

    return jsonify({"ok": True, "records": [row_to_dict(r) for r in rows]})


# ---------- API: Hapus Record (opsional, untuk admin) ----------

@app.route("/api/records/<record_id>", methods=["DELETE"])
def delete_record(record_id):
    db = get_db()
    db.execute("DELETE FROM records WHERE id = ?", (record_id,))
    db.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    print(f"Database siap di: {DB_PATH}")
    app.run(host="0.0.0.0", port=5000, debug=True)
