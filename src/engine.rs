//! Thread-safe access to the real Conway implementation in the shared core.
use std::sync::atomic::{AtomicU64, Ordering};

pub struct ConwayAutomatonEngine {
    state: AtomicU64,
}
impl ConwayAutomatonEngine {
    pub fn new(seed: u64) -> Self {
        Self {
            state: AtomicU64::new(seed),
        }
    }
    pub fn state(&self) -> u64 {
        self.state.load(Ordering::Acquire)
    }
    /// Every successful call advances exactly one generation, including under contention.
    pub fn step(&self) -> u64 {
        let mut current = self.state();
        loop {
            let next = qmoosa_core::life_step(current);
            match self.state.compare_exchange_weak(
                current,
                next,
                Ordering::AcqRel,
                Ordering::Acquire,
            ) {
                Ok(_) => return next,
                Err(actual) => current = actual,
            }
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    #[test]
    fn uses_real_conway_rules() {
        let seed = (1 << 26) | (1 << 27) | (1 << 28);
        let engine = ConwayAutomatonEngine::new(seed);
        assert_eq!(engine.step(), (1 << 19) | (1 << 27) | (1 << 35));
        assert_eq!(engine.step(), seed);
    }
    #[test]
    fn concurrent_steps_are_linearizable() {
        let seed = 0x00000000000e0a04;
        let engine = Arc::new(ConwayAutomatonEngine::new(seed));
        let mut threads = Vec::new();
        for _ in 0..4 {
            let engine = Arc::clone(&engine);
            threads.push(std::thread::spawn(move || {
                for _ in 0..3 {
                    engine.step();
                }
            }));
        }
        for thread in threads {
            thread.join().unwrap();
        }
        let mut expected = seed;
        for _ in 0..12 {
            expected = qmoosa_core::life_step(expected);
        }
        assert_eq!(engine.state(), expected);
    }
}
