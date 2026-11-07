use std::thread::sleep;
use std::time::Duration;

use anyhow::Result;
use esp_idf_svc::hal::ledc::config::TimerConfig;
use esp_idf_svc::hal::ledc::{LedcDriver, Resolution};
use esp_idf_svc::hal::prelude::*;
use log::warn;

pub const REST_ANGLE: f32 = 0.0;
const STRIKE_ANGLE: f32 = 180.0;
const PAUSE: Duration = Duration::from_millis(300); // time spent at the strike position
// The strike stays fast so the chime rings well, but the way back is slow:
// a sudden return is what makes the servo loud.
const RETURN_DURATION_MS: u32 = 1500; // to go back to rest
const STRIKE_GAP: Duration = Duration::from_secs(3); // after each strike, to count them by ear

const FREQUENCY_HZ: u32 = 50; // of the servo signal
const PERIOD_US: u32 = 1_000_000 / FREQUENCY_HZ;
// One step per period of the servo signal, finer would be useless.
const STEP_MS: u32 = 1000 / FREQUENCY_HZ;

pub fn timer_config() -> TimerConfig {
    TimerConfig::new()
        .frequency(FREQUENCY_HZ.Hz())
        .resolution(Resolution::Bits14)
}

pub struct Servo {
    driver: LedcDriver<'static>,
    max_duty: u32,
}

impl Servo {
    pub fn new(driver: LedcDriver<'static>) -> Self {
        let max_duty = driver.get_max_duty();
        Self { driver, max_duty }
    }

    pub fn set_angle(&mut self, angle: f32) -> Result<()> {
        let us = 500.0 + (angle / 180.0) * 1900.0; // 0 deg = 500 us, 180 deg = 2400 us
        let duty = us * self.max_duty as f32 / PERIOD_US as f32;
        self.driver.set_duty(duty as u32)?;
        Ok(())
    }

    /// Go from one angle to another in small steps, over RETURN_DURATION_MS.
    fn move_slowly(&mut self, start: f32, end: f32) -> Result<()> {
        let steps = (RETURN_DURATION_MS / STEP_MS).max(1);
        for step in 1..=steps {
            self.set_angle(start + (end - start) * step as f32 / steps as f32)?;
            sleep(Duration::from_millis(STEP_MS.into()));
        }
        Ok(())
    }

    fn try_strike(&mut self, times: u32) -> Result<()> {
        for _ in 0..times {
            self.set_angle(STRIKE_ANGLE)?;
            sleep(PAUSE);
            self.move_slowly(STRIKE_ANGLE, REST_ANGLE)?;
            sleep(STRIKE_GAP);
        }
        Ok(())
    }

    pub fn strike(&mut self, times: u32) {
        if let Err(e) = self.try_strike(times) {
            warn!("strike error: {e}");
        }
    }
}
