//! Shared core. Network status is reported only by an explicit RPC probe.
use aes_gcm::{
    Aes256Gcm, KeyInit,
    aead::{Aead, AeadCore, OsRng, Payload},
};
use hkdf::Hkdf;
use ml_kem::{
    MlKem768,
    kem::{Decapsulate, Encapsulate, Kem},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use zeroize::Zeroizing;

/// 8x8 Conway B3/S23, finite dead boundaries. Bit (8*y+x) is cell (x,y).
pub fn life_step(board: u64) -> u64 {
    let mut next = 0;
    for y in 0i32..8 {
        for x in 0i32..8 {
            let mut neighbors = 0;
            for dy in -1..=1 {
                for dx in -1..=1 {
                    let (nx, ny) = (x + dx, y + dy);
                    if (dx != 0 || dy != 0) && (0..8).contains(&nx) && (0..8).contains(&ny) {
                        neighbors += ((board >> (ny * 8 + nx)) & 1) as u8;
                    }
                }
            }
            let bit = 1u64 << (y * 8 + x);
            if neighbors == 3 || (neighbors == 2 && board & bit != 0) {
                next |= bit;
            }
        }
    }
    next
}

pub fn life(board: u64, steps: u32) -> Result<Value, String> {
    if steps > 10_000 {
        return Err("steps must be between 0 and 10000".into());
    }
    let mut state = board;
    for _ in 0..steps {
        state = life_step(state);
    }
    Ok(
        json!({"board":format!("{state:016x}"),"alive":state.count_ones(),"steps":steps,
        "rule":"B3/S23","boundary":"finite","width":8}),
    )
}

fn derive_key(secret: &[u8], transcript: &[u8]) -> Result<[u8; 32], String> {
    let mut key = [0u8; 32];
    Hkdf::<Sha256>::new(Some(transcript), secret)
        .expand(b"qmoosa/mlkem768/aes256gcm/demo/v1", &mut key)
        .map_err(|_| "KDF failed")?;
    Ok(key)
}

/// Ephemeral in-process demonstration. No peer authentication or persistent keys.
pub fn pqc_check() -> Result<Value, String> {
    let (dk, ek) = MlKem768::generate_keypair();
    let (ct, sender_secret) = ek.encapsulate();
    let sender_secret = Zeroizing::new(sender_secret);
    let receiver_secret = Zeroizing::new(dk.decapsulate(&ct));
    if sender_secret.as_slice() != receiver_secret.as_slice() {
        return Err("ML-KEM shared-secret mismatch".into());
    }
    let mut modified_ct = ct;
    modified_ct[0] ^= 1;
    let rejected_secret = Zeroizing::new(dk.decapsulate(&modified_ct));
    if rejected_secret.as_slice() == sender_secret.as_slice() {
        return Err("KEM mutation check failed".into());
    }
    let sender_key = Zeroizing::new(derive_key(sender_secret.as_slice(), &ct)?);
    let receiver_key = Zeroizing::new(derive_key(receiver_secret.as_slice(), &ct)?);
    let sender = Aes256Gcm::new_from_slice(sender_key.as_slice()).map_err(|_| "invalid key")?;
    let receiver = Aes256Gcm::new_from_slice(receiver_key.as_slice()).map_err(|_| "invalid key")?;
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng);
    let message = b"QMoosa: verify behavior, then trust the result.";
    let aad = b"qmoosa-demo-v1";
    let encrypted = sender
        .encrypt(&nonce, Payload { msg: message, aad })
        .map_err(|_| "encryption failed")?;
    let recovered = receiver
        .decrypt(
            &nonce,
            Payload {
                msg: &encrypted,
                aad,
            },
        )
        .map_err(|_| "decryption failed")?;
    if recovered != message {
        return Err("plaintext mismatch".into());
    }
    let mut tampered = encrypted.clone();
    tampered[0] ^= 1;
    if receiver
        .decrypt(
            &nonce,
            Payload {
                msg: &tampered,
                aad,
            },
        )
        .is_ok()
    {
        return Err("AEAD accepted modified ciphertext".into());
    }
    let hash = Sha256::digest(ct)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<String>();
    Ok(
        json!({"status":"passed","algorithm":"ML-KEM-768","payload_cipher":"AES-256-GCM",
        "shared_secret_match":true,"kem_mutation_rejected":true,"payload_roundtrip":true,
        "payload_tamper_rejected":true,"kem_ciphertext_bytes":ct.len(),
        "encrypted_payload_bytes":encrypted.len(),"ciphertext_sha256":hash,
        "scope":"ephemeral in-process demonstration; no peer authentication or key storage",
        "certification":"not FIPS validated; dependency and application not independently audited"}),
    )
}

pub fn cli(args: Vec<String>) -> Result<(), String> {
    let result = match args.first().map(String::as_str).unwrap_or("self-check") {
        "self-check" if args.len() <= 1 => {
            let seed = (1 << 26) | (1 << 27) | (1 << 28);
            if life_step(life_step(seed)) != seed {
                return Err("Conway oscillator failed".into());
            }
            json!({"core_version":env!("CARGO_PKG_VERSION"),"life":life(seed,2)?,"pqc":pqc_check()?,
                "rpc":"not probed: run python app.py rpc","agents":"not implemented"})
        }
        "pqc" if args.len() == 1 => pqc_check()?,
        "life" if args.len() == 3 => {
            let board = u64::from_str_radix(args[1].trim_start_matches("0x"), 16)
                .map_err(|_| "board must be a 64-bit hex integer")?;
            let steps = args[2]
                .parse::<u32>()
                .map_err(|_| "steps must be an integer")?;
            life(board, steps)?
        }
        "help" | "--help" => json!({"usage":["cargo run -- self-check","cargo run -- pqc",
            "cargo run -- life HEX_BOARD STEPS","python app.py serve"]}),
        _ => return Err("usage: self-check | pqc | life HEX_BOARD STEPS | --help".into()),
    };
    println!(
        "{}",
        serde_json::to_string_pretty(&result).map_err(|e| e.to_string())?
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn board(cells: &[(u32, u32)]) -> u64 {
        cells.iter().fold(0, |b, (x, y)| b | (1 << (8 * y + x)))
    }
    #[test]
    fn empty_and_single_cell_die() {
        assert_eq!(life_step(0), 0);
        assert_eq!(life_step(1 << 27), 0);
    }
    #[test]
    fn block_is_stable() {
        let b = board(&[(2, 2), (3, 2), (2, 3), (3, 3)]);
        assert_eq!(life_step(b), b);
    }
    #[test]
    fn blinker_oscillates() {
        let h = board(&[(2, 3), (3, 3), (4, 3)]);
        let v = board(&[(3, 2), (3, 3), (3, 4)]);
        assert_eq!(life_step(h), v);
        assert_eq!(life_step(v), h);
    }
    #[test]
    fn glider_moves_diagonally() {
        let mut b = board(&[(2, 1), (3, 2), (1, 3), (2, 3), (3, 3)]);
        for _ in 0..4 {
            b = life_step(b);
        }
        assert_eq!(b, board(&[(3, 2), (4, 3), (2, 4), (3, 4), (4, 4)]));
    }
    #[test]
    fn edges_do_not_wrap() {
        assert_eq!(life_step(board(&[(7, 2), (0, 3), (7, 4)])) & (1 << 24), 0);
    }
    #[test]
    fn work_limit() {
        assert!(life(1, 10001).is_err());
        assert_eq!(life(1, 0).unwrap()["board"], "0000000000000001");
    }
    #[test]
    fn pqc_roundtrip_and_tamper_checks() {
        let a = pqc_check().unwrap();
        let b = pqc_check().unwrap();
        assert_eq!(a["kem_ciphertext_bytes"], 1088);
        assert_eq!(a["payload_tamper_rejected"], true);
        assert_ne!(a["ciphertext_sha256"], b["ciphertext_sha256"]);
    }
    #[test]
    fn cli_rejects_invalid_input() {
        assert!(cli(vec!["unknown".into()]).is_err());
        assert!(cli(vec!["life".into(), "nope".into(), "1".into()]).is_err());
        assert!(cli(vec!["life".into(), "1".into(), "10001".into()]).is_err());
    }
}
