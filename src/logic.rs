//! Pure logic, with no access to the hardware: it can be tested on the computer
//! with `rustc --edition 2021 --test src/logic.rs -o /tmp/logic && /tmp/logic`.

/// A list made only of unknown names: see [`find_new`].
#[derive(Debug, PartialEq)]
pub struct Anomaly;

/// Return the names that should ring.
///
/// The first pass (`seen` is `None`) rings nothing: it only sets the reference.
///
/// A list made only of unknown names rings nothing either. It points to an
/// anomaly, like a changed response format, and not to real events: without
/// this guard, a list that keeps changing could ring at every check, forever.
pub fn find_new(names: &[String], seen: Option<&[String]>) -> Result<Vec<String>, Anomaly> {
    let Some(seen) = seen else {
        return Ok(Vec::new());
    };
    let new: Vec<String> = names.iter().filter(|n| !seen.contains(n)).cloned().collect();
    if new.len() == names.len() {
        return Err(Anomaly);
    }
    Ok(new)
}

/// Return the updated seen list, newest first, capped at `max` names.
pub fn remember(names: &[String], seen: Option<&[String]>, max: usize) -> Vec<String> {
    let older = seen.unwrap_or(&[]).iter().filter(|n| !names.contains(n));
    names.iter().chain(older).take(max).cloned().collect()
}

/// Read a URI like "/strike?servo=1&times=2".
///
/// Return the servo number (from 1) and the number of strikes, or `None` when
/// the call is invalid and nothing should ring.
pub fn parse_strike_query(uri: &str, servo_count: usize, max_times: u32) -> Option<(usize, u32)> {
    let query = uri.split_once('?').map_or("", |(_, query)| query);
    let mut servo = None;
    let mut times = "1";
    for pair in query.split('&') {
        match pair.split_once('=') {
            Some(("servo", value)) => servo = Some(value),
            Some(("times", value)) => times = value,
            _ => {}
        }
    }
    let servo: usize = servo?.parse().ok()?;
    let times: u32 = times.parse().ok()?;
    let valid = (1..=servo_count).contains(&servo) && (1..=max_times).contains(&times);
    valid.then_some((servo, times))
}

/// Read the names of the TNS CSV, block by block.
///
/// The CSV is never held in memory as a whole: only the line being read is.
#[derive(Default)]
pub struct TnsCsv {
    line: Vec<u8>,
    header_seen: bool,
    names: Vec<String>,
}

impl TnsCsv {
    pub fn push(&mut self, block: &[u8]) -> Result<(), &'static str> {
        for &byte in block {
            if byte == b'\n' {
                self.end_line()?;
            } else {
                self.line.push(byte);
            }
        }
        Ok(())
    }

    /// Return the names, newest first.
    pub fn finish(mut self) -> Result<Vec<String>, &'static str> {
        if !self.line.is_empty() {
            self.end_line()?; // the last line may have no newline
        }
        Ok(self.names)
    }

    fn end_line(&mut self) -> Result<(), &'static str> {
        let line = std::mem::take(&mut self.line);
        if !self.header_seen {
            if !line.starts_with(b"\"ID\"") {
                return Err("unexpected response");
            }
            self.header_seen = true;
            return Ok(());
        }
        // Lines look like: "ID","Name","RA",... and the name is the second field.
        if let Some(name) = String::from_utf8_lossy(&line).split("\",\"").nth(1) {
            self.names.push(name.to_string());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(names: &[&str]) -> Vec<String> {
        names.iter().map(|n| n.to_string()).collect()
    }

    #[test]
    fn first_pass_rings_nothing() {
        assert_eq!(find_new(&strings(&["a", "b"]), None), Ok(vec![]));
    }

    #[test]
    fn new_names_ring() {
        let seen = strings(&["b", "c"]);
        assert_eq!(find_new(&strings(&["a", "b"]), Some(&seen)), Ok(strings(&["a"])));
    }

    #[test]
    fn only_unknown_names_is_an_anomaly() {
        let seen = strings(&["c"]);
        assert_eq!(find_new(&strings(&["a", "b"]), Some(&seen)), Err(Anomaly));
    }

    #[test]
    fn remember_keeps_newest_first_and_caps() {
        let seen = strings(&["b", "c", "d"]);
        assert_eq!(remember(&strings(&["a", "b"]), Some(&seen), 3), strings(&["a", "b", "c"]));
        assert_eq!(remember(&strings(&["a"]), None, 3), strings(&["a"]));
    }

    #[test]
    fn strike_query() {
        assert_eq!(parse_strike_query("/strike?servo=1", 2, 5), Some((1, 1)));
        assert_eq!(parse_strike_query("/strike?servo=2&times=3", 2, 5), Some((2, 3)));
        assert_eq!(parse_strike_query("/strike", 2, 5), None);
        assert_eq!(parse_strike_query("/strike?servo=3", 2, 5), None);
        assert_eq!(parse_strike_query("/strike?servo=0", 2, 5), None);
        assert_eq!(parse_strike_query("/strike?servo=1&times=6", 2, 5), None);
        assert_eq!(parse_strike_query("/strike?servo=x", 2, 5), None);
    }

    #[test]
    fn tns_csv_across_blocks() {
        let csv = b"\"ID\",\"Name\",\"RA\"\r\n\"1\",\"SN 2026abc\",\"12\"\r\n\"2\",\"SN 2026abd\",\"13\"";
        let mut parser = TnsCsv::default();
        for block in csv.chunks(7) {
            parser.push(block).unwrap();
        }
        assert_eq!(parser.finish(), Ok(strings(&["SN 2026abc", "SN 2026abd"])));
    }

    #[test]
    fn tns_csv_rejects_other_content() {
        let mut parser = TnsCsv::default();
        assert_eq!(parser.push(b"<html>\n"), Err("unexpected response"));
    }
}
