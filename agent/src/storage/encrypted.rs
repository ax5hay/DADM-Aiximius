//! SQLite-backed store with AES-GCM encryption of sensitive columns and optional full-DB encryption.
//! Key derived from device-bound secret (in production: Secure Enclave / Keystore / DPAPI).

use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm,
};
use rand::RngCore;
use rusqlite::{Connection, params};
use std::path::Path;
use std::sync::Mutex;
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};

const NONCE_LEN: usize = 12;
const KEY_LEN: usize = 32;

fn derive_key(seed: &[u8]) -> [u8; KEY_LEN] {
    use ring::digest;
    let mut out = [0u8; KEY_LEN];
    let h = digest::digest(&digest::SHA256, seed);
    out[..h.as_ref().len().min(KEY_LEN)].copy_from_slice(h.as_ref());
    out
}

fn encrypt(key: &[u8; KEY_LEN], plaintext: &[u8]) -> Result<String, aes_gcm::Error> {
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| aes_gcm::Error)?;
    let mut nonce = [0u8; NONCE_LEN];
    rand::thread_rng().fill_bytes(&mut nonce);
    let ciphertext = cipher.encrypt((&nonce).into(), plaintext)?;
    let mut out = nonce.to_vec();
    out.extend(ciphertext);
    Ok(BASE64.encode(&out))
}

fn decrypt(key: &[u8; KEY_LEN], encoded: &str) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
    let raw = BASE64.decode(encoded)?;
    if raw.len() < NONCE_LEN {
        return Err("payload too short".into());
    }
    let (nonce, ct) = raw.split_at(NONCE_LEN);
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|e| format!("{:?}", e))?;
    Ok(cipher.decrypt(nonce.into(), ct)?)
}

pub struct SecureStore {
    conn: Mutex<Connection>,
    key: [u8; KEY_LEN],
}

impl SecureStore {
    /// Open or create DB at path. Key is derived from `secret` (in production: device-bound).
    pub fn open(path: &Path, secret: &[u8]) -> Result<Self, rusqlite::Error> {
        let conn = Connection::open(path)?;
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                ts INTEGER NOT NULL,
                kind TEXT NOT NULL,
                payload_enc TEXT NOT NULL,
                risk_score REAL
            );
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
            "#,
        )?;
        let key = derive_key(secret);
        Ok(Self {
            conn: Mutex::new(conn),
            key,
        })
    }

    /// Insert event (payload stored encrypted)
    pub fn insert_event(
        &self,
        id: &str,
        ts: i64,
        kind: &str,
        payload_json: &str,
        risk_score: Option<f32>,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let enc = encrypt(&self.key, payload_json.as_bytes())?;
        self.conn.lock().unwrap().execute(
            "INSERT OR REPLACE INTO events (id, ts, kind, payload_enc, risk_score) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![id, ts, kind, enc, risk_score],
        )?;
        Ok(())
    }

    /// Read event by id (decrypt payload)
    pub fn get_event(&self, id: &str) -> Result<Option<(i64, String, Option<f32>)>, Box<dyn std::error::Error + Send + Sync>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT ts, payload_enc, risk_score FROM events WHERE id = ?1")?;
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            let ts: i64 = row.get(0)?;
            let enc: String = row.get(1)?;
            let score: Option<f32> = row.get(2)?;
            let plain = decrypt(&self.key, &enc)?;
            let payload = String::from_utf8(plain).unwrap_or_default();
            return Ok(Some((ts, payload, score)));
        }
        Ok(None)
    }

    /// Retention: delete events older than given timestamp
    pub fn prune_before(&self, ts: i64) -> Result<u64, rusqlite::Error> {
        let n = self.conn.lock().unwrap().execute("DELETE FROM events WHERE ts < ?1", params![ts])?;
        Ok(n as u64)
    }
}
