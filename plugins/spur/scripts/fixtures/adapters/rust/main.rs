use tracing_chrome::ChromeLayerBuilder;
use tracing_subscriber::prelude::*;

#[tracing::instrument]
fn parse_row(i: u32) -> u32 { i * 2 }

#[tracing::instrument]
fn load() -> u32 { (0..3).map(parse_row).sum() }

fn main() {
    let (chrome_layer, _guard) = ChromeLayerBuilder::new().file("trace.json").build();
    tracing_subscriber::registry().with(chrome_layer).init();
    println!("{}", load());
}
