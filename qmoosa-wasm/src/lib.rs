#[cfg(target_arch = "wasm32")]
mod browser {
    use wasm_bindgen::prelude::*;
    #[wasm_bindgen]
    pub fn life(board: &str, steps: u32) -> Result<String, JsValue> {
        let board = u64::from_str_radix(board.trim_start_matches("0x"), 16)
            .map_err(|_| JsValue::from_str("Invalid 64-bit board"))?;
        let output = qmoosa_core::life(board, steps).map_err(|e| JsValue::from_str(&e))?;
        serde_json::to_string(&output).map_err(|_| JsValue::from_str("Serialization failed"))
    }
    #[wasm_bindgen]
    pub fn pqc() -> Result<String, JsValue> {
        let output = qmoosa_core::pqc_check().map_err(|e| JsValue::from_str(&e))?;
        serde_json::to_string(&output).map_err(|_| JsValue::from_str("Serialization failed"))
    }
}
