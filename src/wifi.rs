use anyhow::{anyhow, Result};
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::hal::modem::Modem;
use esp_idf_svc::mdns::EspMdns;
use esp_idf_svc::nvs::EspDefaultNvsPartition;
use esp_idf_svc::wifi::{BlockingWifi, ClientConfiguration, Configuration, EspWifi};
use log::{info, warn};

use crate::secrets::{PASSWORD, SSID};

pub const HOSTNAME: &str = "astral-chimes"; // the board answers at astral-chimes.local
// Sent with every request to the catalogs, so they know who is calling.
pub const USER_AGENT: &str = "astral-chimes/0.1 (personal project)";

pub type Wifi = BlockingWifi<EspWifi<'static>>;

pub fn start(modem: Modem, sysloop: EspSystemEventLoop, nvs: EspDefaultNvsPartition) -> Result<Wifi> {
    let mut wifi = BlockingWifi::wrap(EspWifi::new(modem, sysloop.clone(), Some(nvs))?, sysloop)?;
    wifi.set_configuration(&Configuration::Client(ClientConfiguration {
        ssid: SSID.try_into().map_err(|_| anyhow!("SSID too long"))?,
        password: PASSWORD.try_into().map_err(|_| anyhow!("password too long"))?,
        ..Default::default()
    }))?;
    wifi.start()?;
    Ok(wifi)
}

/// Connect, or log why it failed: the program goes on, and retries at the next check.
pub fn connect(wifi: &mut Wifi) {
    let result = wifi.connect().and_then(|()| wifi.wait_netif_up());
    match result.and_then(|()| wifi.wifi().sta_netif().get_ip_info()) {
        Ok(ip_info) => info!("wifi ok: {}", ip_info.ip),
        Err(e) => warn!("wifi failed: {e}"),
    }
}

pub fn is_connected(wifi: &Wifi) -> bool {
    wifi.is_connected().unwrap_or(false)
}

/// Keep the returned value alive: dropping it stops mDNS.
pub fn start_mdns() -> Result<EspMdns> {
    let mut mdns = EspMdns::take()?;
    mdns.set_hostname(HOSTNAME)?;
    Ok(mdns)
}
