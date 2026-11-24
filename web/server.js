
const express = require("express");
const sqlite3 = require("sqlite3").verbose();
const path = require("path");
const saunaMqtt = require("./mqtt");

const app = express();
const PORT = 3000;

// Database location
const dbPath = path.join(
    __dirname, "..", "database", "sauna.db"
);

// Connect with read and write permissions
const db = new sqlite3.Database(
    dbPath,
    sqlite3.OPEN_READWRITE,
    (err) => {
        if (err) {
            console.error(err.message);
        } else {
            console.log("Connected to sauna database!");
        }
    }
);

db.configure("busyTimeout", 5000);

// Middleware
app.use(express.json());

app.use(express.static(
    path.join(__dirname, "public")
));

// =============================
// SENSOR MEASUREMENTS
// =============================

// Get latest measurement
app.get("/api/latest", (req, res) => {
    db.get(
        "SELECT * FROM measurements ORDER BY id DESC LIMIT 1",
        (err, row) => {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            res.json(row || {});
        }
    );
});

// Get latest 20 measurements
app.get("/api/measurements", (req, res) => {
    db.all(
        "SELECT * FROM measurements ORDER BY id DESC LIMIT 20",
        (err, rows) => {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            res.json(rows);
        }
    );
});

// =============================
// USER PROFILES
// =============================

// Validate profile information
function validProfile(data) {
    return (
        typeof data.name === "string" &&
        data.name.trim().length > 0 &&
        Number.isFinite(data.target_temperature) &&
        data.target_temperature >= 20 &&
        data.target_temperature <= 100 &&
        Number.isFinite(data.target_humidity) &&
        data.target_humidity >= 0 &&
        data.target_humidity <= 100
    );
}

// Get all profiles
app.get("/api/profiles", (req, res) => {
    db.all(
        "SELECT * FROM profiles ORDER BY id",
        (err, rows) => {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            res.json(rows);
        }
    );
});

// Get active profile
app.get("/api/profiles/active", (req, res) => {
    db.get(
        "SELECT * FROM profiles WHERE active = 1",
        (err, row) => {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            res.json(row || {});
        }
    );
});

// Create new profile
app.post("/api/profiles", (req, res) => {

    if (!validProfile(req.body)) {
        return res.status(400).json({
            error: "Invalid profile information"
        });
    }

    const {
        name,
        target_temperature,
        target_humidity
    } = req.body;

    db.run(
        `INSERT INTO profiles
        (name, target_temperature, target_humidity, active)
        VALUES (?, ?, ?, 0)`,

        [
            name.trim(),
            target_temperature,
            target_humidity
        ],

        function (err) {
            if (err) {
                return res.status(400).json({
                    error: err.message
                });
            }

            res.status(201).json({
                message: "Profile created",
                id: this.lastID
            });
        }
    );
});

// Update existing profile
app.put("/api/profiles/:id", (req, res) => {

    if (!validProfile(req.body)) {
        return res.status(400).json({
            error: "Invalid profile information"
        });
    }

    const {
        name,
        target_temperature,
        target_humidity
    } = req.body;

    db.run(
        `UPDATE profiles
         SET name = ?,
             target_temperature = ?,
             target_humidity = ?
         WHERE id = ?`,

        [
            name.trim(),
            target_temperature,
            target_humidity,
            req.params.id
        ],

        function (err) {
            if (err) {
                return res.status(400).json({
                    error: err.message
                });
            }

            if (this.changes === 0) {
                return res.status(404).json({
                    error: "Profile not found"
                });
            }

            res.json({
                message: "Profile updated"
            });
        }
    );
});

// Select active profile
app.put("/api/profiles/:id/activate", (req, res) => {

    db.run(
        `UPDATE profiles
         SET active = CASE WHEN id = ? THEN 1 ELSE 0 END
         WHERE EXISTS (
             SELECT 1 FROM profiles WHERE id = ?
         )`,

        [req.params.id, req.params.id],

        function (err) {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            if (this.changes === 0) {
                return res.status(404).json({
                    error: "Profile not found"
                });
            }

            res.json({
                message: "Profile activated"
            });
        }
    );
});

// Delete profile
app.delete("/api/profiles/:id", (req, res) => {

    db.run(
        "DELETE FROM profiles WHERE id = ? AND active = 0",
        [req.params.id],

        function (err) {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            if (this.changes === 0) {
                return res.status(400).json({
                    error: "Profile not found or currently active"
                });
            }

            res.json({
                message: "Profile deleted"
            });
        }
    );
});

// Get live sauna readiness status
app.get("/api/status", (req, res) => {
    res.json(saunaMqtt.getStatus());
});
// =============================
// START SERVER
// =============================

app.listen(PORT, "0.0.0.0", () => {
    console.log("Smart Sauna web server running!");
    console.log(`Port: ${PORT}`);
});
