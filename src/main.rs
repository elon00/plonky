fn main() {
    if let Err(error) = qmoosa_core::cli(std::env::args().skip(1).collect()) {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
