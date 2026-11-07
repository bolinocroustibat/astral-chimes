//! Ring a chime for each new confirmed supernova, and a second one for each new
//! gravitational wave event.

mod catalogs;
mod http_server;
mod logic;
mod secrets;
mod servos;
mod wifi;

use std::sync::mpsc::{self, Receiver};
use std::thread::sleep;
use std::time::{Duration, Instant};

use anyhow::Result;
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::hal::gpio::{Gpio0, Input, PinDriver, Pull};
use esp_idf_svc::hal::ledc::{LedcDriver, LedcTimerDriver};
use esp_idf_svc::hal::peripherals::Peripherals;
use esp_idf_svc::log::EspLogger;
use esp_idf_svc::nvs::EspDefaultNvsPartition;
use log::{info, warn};

use http_server::StrikeRequest;
use logic::{find_new, remember, Anomaly};
use servos::{Servo, REST_ANGLE};

const CHECK_INTERVAL: Duration = Duration::from_secs(300); // between two checks of the catalogs
const MAX_SEEN: usize = 40; // names remembered, must stay above the page size of each catalog
const TEST_DELAY: Duration = Duration::from_secs(2); // between the button press and the first test strike
const TEST_GAP: Duration = Duration::from_secs(5); // extra time between two servos on a test strike

type Button = PinDriver<'static, Gpio0, Input>;

fn main() -> Result<()> {
    esp_idf_svc::sys::link_patches();
    EspLogger::initialize_default();

    let peripherals = Peripherals::take()?;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs = EspDefaultNvsPartition::take()?;

    // Both servos share one timer, which must outlive them.
    let timer = Box::leak(Box::new(LedcTimerDriver::new(
        peripherals.ledc.timer0,
        &servos::timer_config(),
    )?));
    let mut servos = [
        // supernovae
        Servo::new(LedcDriver::new(peripherals.ledc.channel0, &*timer, peripherals.pins.gpio13)?),
        // gravitational waves
        Servo::new(LedcDriver::new(peripherals.ledc.channel1, &*timer, peripherals.pins.gpio27)?),
    ];
    for servo in &mut servos {
        servo.set_angle(REST_ANGLE)?;
    }
    sleep(Duration::from_secs(1));

    // BOOT button, reads low when pressed
    let mut button = PinDriver::input(peripherals.pins.gpio0)?;
    button.set_pull(Pull::Up)?;

    let mut wifi = wifi::start(peripherals.modem, sysloop, nvs)?;
    wifi::connect(&mut wifi);
    let _mdns = wifi::start_mdns()?;
    let (strikes, strike_requests) = mpsc::channel();
    let _server = http_server::start(strikes, servos.len())?;

    let mut seen_supernovae = None;
    let mut seen_gravitational_waves = None;
    loop {
        if !wifi::is_connected(&wifi) {
            wifi::connect(&mut wifi);
        }
        let [supernova_servo, gravitational_wave_servo] = &mut servos;
        seen_supernovae = check("supernova", catalogs::fetch_supernovae, seen_supernovae, supernova_servo);
        seen_gravitational_waves = check(
            "gravitational wave",
            catalogs::fetch_gravitational_waves,
            seen_gravitational_waves,
            gravitational_wave_servo,
        );
        wait_and_watch_inputs(CHECK_INTERVAL, &strike_requests, &button, &mut servos);
    }
}

/// Fetch the latest events, strike once per new one, return the updated seen list.
fn check(
    label: &str,
    fetch: fn() -> Result<Vec<String>>,
    seen: Option<Vec<String>>,
    servo: &mut Servo,
) -> Option<Vec<String>> {
    let names = match fetch() {
        Ok(names) => names,
        Err(e) => {
            warn!("{label} error: {e:#}");
            return seen;
        }
    };
    info!("{label} names: {}", names.len());
    if names.is_empty() {
        return seen; // an empty answer must not replace the reference
    }
    let new = find_new(&names, seen.as_deref()).unwrap_or_else(|Anomaly| {
        warn!("{label} anomaly: only unknown names, ignored");
        Vec::new()
    });
    let seen = remember(&names, seen.as_deref(), MAX_SEEN); // before ringing, so nothing rings twice
    for name in new {
        info!("{label} new: {name}");
        servo.strike(1);
    }
    Some(seen)
}

/// Sleep for the given time, while watching the test button and HTTP calls.
///
/// A press on the button strikes all servos. An HTTP call strikes the servo it
/// asks for: the server answers at once, the strike is done here.
fn wait_and_watch_inputs(
    duration: Duration,
    strike_requests: &Receiver<StrikeRequest>,
    button: &Button,
    servos: &mut [Servo],
) {
    let deadline = Instant::now() + duration;
    while Instant::now() < deadline {
        while let Ok((number, times)) = strike_requests.try_recv() {
            info!("http strike {number} {times}");
            servos[number - 1].strike(times);
        }
        if button.is_low() {
            info!("test strike");
            sleep(TEST_DELAY);
            for (index, servo) in servos.iter_mut().enumerate() {
                if index > 0 {
                    sleep(TEST_GAP);
                }
                servo.strike(1);
            }
        }
        sleep(Duration::from_millis(50));
    }
}
