use pyo3::prelude::*;
use std::collections::VecDeque;

#[pyclass]
pub struct RustAudioCore {
    ring: VecDeque<i16>,
    capacity: usize,
}

// Private helpers — not exported to Python
impl RustAudioCore {
    fn read_frames_raw(&mut self, frame_samples: usize, max_frames: usize) -> Vec<Vec<i16>> {
        if frame_samples == 0 || max_frames == 0 {
            return Vec::new();
        }

        let mut out: Vec<Vec<i16>> = Vec::new();
        while self.ring.len() >= frame_samples && out.len() < max_frames {
            let mut frame = Vec::with_capacity(frame_samples);
            for _ in 0..frame_samples {
                if let Some(s) = self.ring.pop_front() {
                    frame.push(s);
                }
            }
            out.push(frame);
        }
        out
    }
}

#[pymethods]
impl RustAudioCore {
    #[new]
    fn new(capacity_samples: usize) -> Self {
        let cap = if capacity_samples == 0 { 16000 * 10 } else { capacity_samples };
        Self {
            ring: VecDeque::with_capacity(cap),
            capacity: cap,
        }
    }

    fn push_audio(&mut self, data: &[u8]) -> usize {
        let samples: Vec<i16> = data
            .chunks_exact(2)
            .map(|b| i16::from_le_bytes([b[0], b[1]]))
            .collect();

        if samples.len() >= self.capacity {
            self.ring.clear();
            let start = samples.len() - self.capacity;
            self.ring.extend(samples[start..].iter().copied());
            return self.capacity;
        }

        let overflow = self
            .ring
            .len()
            .saturating_add(samples.len())
            .saturating_sub(self.capacity);
        for _ in 0..overflow {
            self.ring.pop_front();
        }
        self.ring.extend(samples.iter().copied());
        self.ring.len()
    }

    // Returns frames as little-endian bytes — avoids O(n) Python object creation
    fn read_frames(&mut self, frame_samples: usize, max_frames: usize) -> Vec<Vec<u8>> {
        self.read_frames_raw(frame_samples, max_frames)
            .into_iter()
            .map(|f| f.iter().flat_map(|s| s.to_le_bytes()).collect())
            .collect()
    }

    fn resample(&self, data: &[u8], in_rate: usize, out_rate: usize) -> Vec<u8> {
        let samples: Vec<i16> = data
            .chunks_exact(2)
            .map(|b| i16::from_le_bytes([b[0], b[1]]))
            .collect();

        if in_rate == 0 || out_rate == 0 || samples.is_empty() {
            return data.to_vec();
        }
        if in_rate == out_rate {
            return data.to_vec();
        }

        let out_len = samples.len().saturating_mul(out_rate) / in_rate;
        if out_len == 0 {
            return Vec::new();
        }

        let mut out = Vec::with_capacity(out_len);
        for i in 0..out_len {
            let src_pos = (i as f32) * (in_rate as f32) / (out_rate as f32);
            let left = src_pos.floor() as usize;
            let right = if left + 1 < samples.len() { left + 1 } else { left };
            let frac = src_pos - (left as f32);

            let l = samples[left] as f32;
            let r = samples[right] as f32;
            let value = l * (1.0 - frac) + r * frac;
            out.push(value.round() as i16);
        }

        out.into_iter()
            .flat_map(|s| s.to_le_bytes())
            .collect()
    }
}

#[pymodule]
fn audio_core(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustAudioCore>()?;
    Ok(())
}
