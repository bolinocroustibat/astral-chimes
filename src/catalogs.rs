//! The catalogs that ring: supernovae from the Transient Name Server (TNS),
//! gravitational waves from GraceDB (LIGO/Virgo/KAGRA).

use std::time::Duration;

use anyhow::{anyhow, bail, Result};
use embedded_svc::http::client::Client;
use embedded_svc::http::{Method, Status};
use embedded_svc::io::Read;
use esp_idf_svc::http::client::{Configuration, EspHttpConnection};
use serde::Deserialize;

use crate::logic::TnsCsv;
use crate::wifi::USER_AGENT;

const SUPERNOVAE_URL: &str = "https://www.wis-tns.org/search?format=csv&num_page=20&classified_sne=1\
    &discovered_period_value=30&discovered_period_units=days";

// Significant public alerts only (SIGNIF_LOCKED), not retracted ones (ADVNO).
// Each event weighs about 3 KB of JSON, read in one piece: 3 events keep it small.
const GRAVITATIONAL_WAVES_URL: &str = "https://gracedb.ligo.org/api/superevents/?count=3\
    &query=category%3A+Production+SIGNIF_LOCKED+%26+~ADVNO";
const MAX_JSON_BYTES: usize = 32 * 1024;

/// GET a URL and hand its body to `on_block`, a small block at a time.
fn get(url: &str, mut on_block: impl FnMut(&[u8]) -> Result<()>) -> Result<()> {
    let connection = EspHttpConnection::new(&Configuration {
        crt_bundle_attach: Some(esp_idf_svc::sys::esp_crt_bundle_attach),
        buffer_size: Some(4096), // the response headers must fit in it
        timeout: Some(Duration::from_secs(30)),
        ..Default::default()
    })?;
    let mut client = Client::wrap(connection);
    let mut response = client.request(Method::Get, url, &[("User-Agent", USER_AGENT)])?.submit()?;
    let status = response.status();
    if status != 200 {
        bail!("http {status}");
    }
    let mut block = [0u8; 256];
    loop {
        let count = response.read(&mut block)?;
        if count == 0 {
            return Ok(());
        }
        on_block(&block[..count])?;
    }
}

/// Return the names of the latest confirmed supernovae, newest first.
pub fn fetch_supernovae() -> Result<Vec<String>> {
    let mut csv = TnsCsv::default();
    get(SUPERNOVAE_URL, |block| csv.push(block).map_err(|e| anyhow!(e)))?;
    csv.finish().map_err(|e| anyhow!(e))
}

#[derive(Deserialize)]
struct Superevents {
    superevents: Vec<Superevent>,
}

#[derive(Deserialize)]
struct Superevent {
    superevent_id: String,
}

/// Return the ids of the latest significant gravitational wave events, newest first.
pub fn fetch_gravitational_waves() -> Result<Vec<String>> {
    let mut body = Vec::new();
    get(GRAVITATIONAL_WAVES_URL, |block| {
        if body.len() + block.len() > MAX_JSON_BYTES {
            bail!("response too large");
        }
        body.extend_from_slice(block);
        Ok(())
    })?;
    let data: Superevents =
        serde_json::from_slice(&body).map_err(|e| anyhow!("unexpected response: {e}"))?;
    Ok(data.superevents.into_iter().map(|event| event.superevent_id).collect())
}
