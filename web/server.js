
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
// Initialize sauna state table
function initializeSaunaState(callback) {
    db.run(
        `CREATE TABLE IF NOT EXISTS sauna_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_on INTEGER NOT NULL DEFAULT 0
                CHECK (is_on IN (0, 1)),
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )`,
        (err) => {
            if (err) {
                return callback(err);
            }

            db.run(
                `INSERT OR IGNORE INTO sauna_state (id, is_on)
                 VALUES (1, 0)`,
                callback
            );
        }
    );
}

// Middleware
app.use(express.json());

app.use(express.static(
    path.join(__dirname, "public")
));

// =============================
// SENSOR MEASUREMENTS
// =============================

// Get latest measurement
function getMeasurementSauna(req) {
  const saunaId = req.query.sauna ?? "koti";
  return saunaId === "koti" || saunaId === "ranta" ? saunaId : null;
}

function getRantaFrostProtection(reading) {
  const savedAt = typeof reading.timestamp === "string"
    ? Date.parse(reading.timestamp.replace(" ", "T") + "Z")
    : NaN;

  if (
    !Number.isFinite(reading.temperature) ||
    !Number.isFinite(savedAt) ||
    Date.now() - savedAt > 15_000
  ) {
    return {
      state: "unknown",
      heating_requested: null,
      frost_alarm: null,
    };
  }

  return {
    state: "automatic",
    heating_requested: reading.temperature < 3,
    frost_alarm: reading.temperature < 0,
  };
}

app.get("/api/latest", (req, res) => {
  const saunaId = getMeasurementSauna(req);
  if (saunaId === null) {
    return res.status(400).json({ error: "Saunan pitää olla koti tai ranta." });
  }

  db.get(
    "SELECT * FROM measurements WHERE sauna_id = ? ORDER BY id DESC LIMIT 1",
    [saunaId],
    (err, row) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (saunaId === "ranta" && row) {
        return res.json({
          ...row,
          frost_protection: getRantaFrostProtection(row),
        });
      }

      res.json(row || {});
    }
  );
});


// Get latest 20 measurements
app.get("/api/measurements", (req, res) => {
  const saunaId = getMeasurementSauna(req);
  if (saunaId === null) {
    return res.status(400).json({ error: "Saunan pitää olla koti tai ranta." });
  }

  db.all(
    "SELECT * FROM measurements WHERE sauna_id = ? ORDER BY id DESC LIMIT 20",
    [saunaId],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
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
// SAUNA ON/OFF STATE
// =============================

// Get current sauna state
app.get("/api/sauna/state", (req, res) => {
    db.get(
        "SELECT * FROM sauna_state WHERE id = 1",
        (err, row) => {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            if (!row) {
                return res.status(404).json({
                    error: "Sauna state not found"
                });
            }

            res.json(row);
        }
    );
});

// Change sauna ON/OFF state
app.put("/api/sauna/state", (req, res) => {

    const is_on = req.body?.is_on;

    // Only accept 0 (OFF) or 1 (ON)
    if (is_on !== 0 && is_on !== 1) {
        return res.status(400).json({
            error: "Sauna state must be 0 or 1"
        });
    }

    db.run(
        `UPDATE sauna_state
         SET is_on = ?,
             updated_at = CURRENT_TIMESTAMP
         WHERE id = 1`,

        [is_on],

        function (err) {
            if (err) {
                return res.status(500).json({
                    error: err.message
                });
            }

            if (this.changes === 0) {
                return res.status(404).json({
                    error: "Sauna state not found"
                });
            }

            res.json({
                message: is_on === 1
                    ? "Sauna turned ON"
                    : "Sauna turned OFF",
                is_on: is_on
            });
        }
    );
});
// =============================
// START SERVER
// =============================

initializeSaunaState((err) => {
    if (err) {
        console.error(
            "Failed to initialize sauna state:",
            err.message
        );
        process.exit(1);
    }

    console.log("Sauna state initialized!");

    app.listen(PORT, "0.0.0.0", () => {
        console.log("Smart Sauna web server running!");
        console.log(`Port: ${PORT}`);
    });
});