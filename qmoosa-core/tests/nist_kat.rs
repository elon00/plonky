//! Official ACVP sample KATs. Expanded keys and deterministic randomness are test-only.
#![allow(deprecated)]
use ml_kem::{
    Ciphertext, DecapsulationKey768, EncapsulationKey768, ExpandedKeyEncoding, KeyExport, MlKem768,
    Seed, kem::Decapsulate,
};
use serde_json::Value;
fn fixtures() -> Value {
    serde_json::from_str(include_str!("fixtures/nist-mlkem768.json")).unwrap()
}
fn hex(value: &Value) -> Vec<u8> {
    let value = value.as_str().unwrap();
    (0..value.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&value[i..i + 2], 16).unwrap())
        .collect()
}
#[test]
fn nist_key_generation_matches_full_public_and_private_keys() {
    for case in fixtures()["keyGen"].as_array().unwrap() {
        let mut seed = Seed::default();
        seed[..32].copy_from_slice(&hex(&case["d"]));
        seed[32..].copy_from_slice(&hex(&case["z"]));
        let dk = DecapsulationKey768::from_seed(seed);
        assert_eq!(
            dk.encapsulation_key().to_bytes().as_slice(),
            hex(&case["ek"])
        );
        assert_eq!(dk.to_expanded_bytes().as_slice(), hex(&case["dk"]));
    }
}
#[test]
fn nist_encapsulation_matches_ciphertext_and_secret() {
    for case in fixtures()["encapsulation"].as_array().unwrap() {
        let raw = hex(&case["ek"]);
        let encoded = raw.as_slice().try_into().unwrap();
        let ek = EncapsulationKey768::new(&encoded).unwrap();
        let raw = hex(&case["m"]);
        let randomness = raw.as_slice().try_into().unwrap();
        let (ct, key) = ek.encapsulate_deterministic(&randomness);
        assert_eq!(ct.as_slice(), hex(&case["c"]));
        assert_eq!(key.as_slice(), hex(&case["k"]));
    }
}
#[test]
fn nist_decapsulation_including_implicit_rejection() {
    for case in fixtures()["decapsulation"].as_array().unwrap() {
        let raw = hex(&case["dk"]);
        let encoded = raw.as_slice().try_into().unwrap();
        let dk = DecapsulationKey768::from_expanded_bytes(&encoded).unwrap();
        let ct: Ciphertext<MlKem768> = hex(&case["c"]).as_slice().try_into().unwrap();
        assert_eq!(dk.decapsulate(&ct).as_slice(), hex(&case["k"]));
    }
}
#[test]
fn nist_encapsulation_key_validation() {
    for case in fixtures()["encapsulationKeyCheck"].as_array().unwrap() {
        let raw = hex(&case["ek"]);
        let encoded = raw.as_slice().try_into().unwrap();
        assert_eq!(
            EncapsulationKey768::new(&encoded).is_ok(),
            case["testPassed"].as_bool().unwrap()
        );
    }
}
#[test]
fn nist_decapsulation_key_validation() {
    for case in fixtures()["decapsulationKeyCheck"].as_array().unwrap() {
        let raw = hex(&case["dk"]);
        let encoded = raw.as_slice().try_into().unwrap();
        assert_eq!(
            DecapsulationKey768::from_expanded_bytes(&encoded).is_ok(),
            case["testPassed"].as_bool().unwrap()
        );
    }
}
