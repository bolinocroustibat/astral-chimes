use std::sync::mpsc::Sender;

use anyhow::Result;
use embedded_svc::http::Method;
use embedded_svc::io::Write;
use esp_idf_svc::http::server::{Configuration, EspHttpServer};

use crate::logic::parse_strike_query;

const HTTP_PORT: u16 = 80;
const MAX_HTTP_TIMES: u32 = 5; // strikes allowed in one HTTP call
const USAGE: &str = "usage: /strike?servo=N&times=K\n";

/// A servo number (from 1) and a number of strikes.
pub type StrikeRequest = (usize, u32);

/// Start the server, which runs in its own task.
///
/// It answers at once and sends the strikes to `strikes`: the main loop does
/// them, as it owns the servos. Other paths get a 404 from the server itself.
pub fn start(strikes: Sender<StrikeRequest>, servo_count: usize) -> Result<EspHttpServer<'static>> {
    let mut server = EspHttpServer::new(&Configuration {
        http_port: HTTP_PORT,
        ..Default::default()
    })?;
    server.fn_handler("/strike", Method::Get, move |request| -> Result<()> {
        let parsed = parse_strike_query(request.uri(), servo_count, MAX_HTTP_TIMES);
        let (status, body) = if parsed.is_some() { (200, "ok\n") } else { (400, USAGE) };
        let mut response = request.into_response(status, None, &[("Content-Type", "text/plain")])?;
        response.write_all(body.as_bytes())?;
        if let Some(strike) = parsed {
            strikes.send(strike)?;
        }
        Ok(())
    })?;
    Ok(server)
}
