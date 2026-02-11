use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::f64::consts::LN_2;
use std::fs;
use std::io::{self, BufRead, Write};
use std::os::unix::net::UnixDatagram;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Deserialize, Serialize)]
struct PerfStats {
    cycles: Option<f64>,
    instructions: Option<f64>,
    cache_misses: Option<f64>,
    branch_mispredicts: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct KernelEvent {
    timestamp: Option<u64>,
    syscalls: Option<HashMap<String, f64>>,
    iowait_ms: Option<f64>,
    context_switches: Option<f64>,
    page_faults: Option<f64>,
    cpu_percent: Option<f64>,
    ram_percent: Option<f64>,
    perf: Option<PerfStats>,
}

#[derive(Debug, Serialize)]
struct KernelAggregate {
    timestamp: u64,
    syscalls: HashMap<String, f64>,
    iowait_ms: f64,
    context_switches: f64,
    page_faults: f64,
    perf: PerfStats,
    cpu_percent: f64,
    ram_percent: f64,
    hpi: f64,
    cli: f64,
    syscall_entropy: f64,
    state: String,
}

fn main() {
    let socket_path = std::env::var("KACL_SOCKET").unwrap_or_else(|_| "/tmp/kacl.sock".to_string());
    let stream_path = std::env::var("KACL_STREAM_SOCKET").unwrap_or_else(|_| "/tmp/kacl_stream.sock".to_string());
    let latest_payload: Arc<Mutex<Vec<u8>>> = Arc::new(Mutex::new(Vec::new()));
    let responder_payload = Arc::clone(&latest_payload);
    let responder_path = socket_path.clone();
    let _ = fs::remove_file(&responder_path);
    let responder = thread::spawn(move || poll_responder(&responder_path, responder_payload));
    let stream_socket = UnixDatagram::unbound().ok();

    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { continue };
        if line.trim().is_empty() {
            continue;
        }
        let Ok(event) = serde_json::from_str::<KernelEvent>(&line) else { continue };
        let aggregate = aggregate_event(event);
        let payload = match serde_json::to_vec(&aggregate) {
            Ok(data) => data,
            Err(_) => continue,
        };
        if let Ok(mut guard) = latest_payload.lock() {
            *guard = payload.clone();
        }
        let _ = io::stdout().write_all(&payload);
        let _ = io::stdout().write_all(b"\n");
        if let Some(sock) = &stream_socket {
            let _ = sock.send_to(&payload, Path::new(&stream_path));
        }
    }

    let _ = responder.join();
}

fn aggregate_event(event: KernelEvent) -> KernelAggregate {
    let syscalls = event.syscalls.unwrap_or_default();
    let perf = event.perf.unwrap_or(PerfStats {
        cycles: Some(0.0),
        instructions: Some(0.0),
        cache_misses: Some(0.0),
        branch_mispredicts: Some(0.0),
    });
    let iowait_ms = event.iowait_ms.unwrap_or(0.0);
    let context_switches = event.context_switches.unwrap_or(0.0);
    let page_faults = event.page_faults.unwrap_or(0.0);
    let cpu_percent = event.cpu_percent.unwrap_or(0.0);
    let ram_percent = event.ram_percent.unwrap_or(0.0);

    let cpu = normalize(cpu_percent / 100.0);
    let ram = normalize(ram_percent / 100.0);
    let iowait = normalize(iowait_ms / 100.0);
    let cache_miss = normalize(perf.cache_misses.unwrap_or(0.0) / 1_000_000.0);
    let br_mispred = normalize(perf.branch_mispredicts.unwrap_or(0.0) / 1_000_000.0);
    let hpi = normalize(0.3 * cpu + 0.3 * ram + 0.2 * iowait + 0.1 * cache_miss + 0.1 * br_mispred);

    let syscall_entropy = normalized_entropy(&syscalls);
    let context_rate = normalize(context_switches / 10_000.0);
    let cli = normalize(0.5 * hpi + 0.3 * context_rate + 0.2 * syscall_entropy);

    let state = if hpi >= 0.75 || cli >= 0.75 {
        "overload"
    } else if hpi <= 0.3 && cli <= 0.3 {
        "high_throughput"
    } else {
        "stable"
    };

    KernelAggregate {
        timestamp: event
            .timestamp
            .unwrap_or_else(|| SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs()),
        syscalls,
        iowait_ms,
        context_switches,
        page_faults,
        perf,
        cpu_percent,
        ram_percent,
        hpi,
        cli,
        syscall_entropy,
        state: state.to_string(),
    }
}

fn normalize(value: f64) -> f64 {
    if value.is_nan() {
        0.0
    } else {
        value.clamp(0.0, 1.0)
    }
}

fn normalized_entropy(syscalls: &HashMap<String, f64>) -> f64 {
    let total: f64 = syscalls.values().sum();
    if total <= 0.0 {
        return 0.0;
    }
    let mut entropy = 0.0;
    let mut count = 0;
    for value in syscalls.values() {
        if *value <= 0.0 {
            continue;
        }
        let p = value / total;
        entropy -= p * (p.ln() / LN_2);
        count += 1;
    }
    let max_entropy = if count > 1 {
        (count as f64).ln() / LN_2
    } else {
        1.0
    };
    normalize(entropy / max_entropy)
}

fn poll_responder(socket_path: &str, payload: Arc<Mutex<Vec<u8>>>) {
    let socket = match UnixDatagram::bind(Path::new(socket_path)) {
        Ok(sock) => sock,
        Err(_) => return,
    };
    let mut buf = [0u8; 32];
    loop {
        let Ok((size, addr)) = socket.recv_from(&mut buf) else { continue };
        if size == 0 {
            continue;
        }
        let Some(path) = addr.as_pathname() else { continue };
        if let Ok(guard) = payload.lock() {
            if guard.is_empty() {
                continue;
            }
            let _ = socket.send_to(&guard, path);
        }
    }
}
