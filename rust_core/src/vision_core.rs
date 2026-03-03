use std::collections::VecDeque;
use std::sync::Arc;

use pyo3::prelude::*;
use rustdct::{Dct2, DctPlanner};

const PHASH_WEIGHT: f32 = 0.45;
const SSIM_WEIGHT: f32 = 0.35;
const OCR_WEIGHT: f32 = 0.20;

#[pyclass]
pub struct RustSceneChangeDetector {
    last_frame: Option<Vec<u8>>,
    last_width: usize,
    last_height: usize,
    last_phash: Option<u64>,
    last_dhash: Option<u64>,
    last_ocr_text: String,
    dct_plan: Arc<dyn Dct2<f32>>,
}

#[pymethods]
impl RustSceneChangeDetector {
    #[new]
    pub fn new() -> Self {
        let mut planner = DctPlanner::new();
        let dct_plan = planner.plan_dct2(32);
        Self {
            last_frame: None,
            last_width: 0,
            last_height: 0,
            last_phash: None,
            last_dhash: None,
            last_ocr_text: String::new(),
            dct_plan,
        }
    }

    pub fn calculate_scene_score(
        &mut self,
        frame_rgb: Vec<u8>,
        width: usize,
        height: usize,
        current_ocr_text: Option<String>,
    ) -> PyResult<f32> {
        if width == 0 || height == 0 || frame_rgb.is_empty() {
            return Ok(0.0);
        }

        let expected = width.saturating_mul(height).saturating_mul(3);
        if frame_rgb.len() != expected {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "invalid frame bytes: expected {}, got {}",
                expected,
                frame_rgb.len()
            )));
        }

        if self.last_frame.is_none() {
            let phash = phash64(&frame_rgb, width, height, self.dct_plan.as_ref());
            let dhash = dhash64(&frame_rgb, width, height);
            self.last_frame = Some(frame_rgb);
            self.last_width = width;
            self.last_height = height;
            self.last_phash = Some(phash);
            self.last_dhash = Some(dhash);
            self.last_ocr_text = current_ocr_text.unwrap_or_default();
            return Ok(1.0);
        }

        let current_phash = phash64(&frame_rgb, width, height, self.dct_plan.as_ref());
        let current_dhash = dhash64(&frame_rgb, width, height);

        let ph = hamming64(current_phash, self.last_phash.unwrap_or(current_phash));
        let dh = hamming64(current_dhash, self.last_dhash.unwrap_or(current_dhash));
        let hash_delta = (ph + dh) * 0.5;

        let ssim = if self.last_width == width && self.last_height == height {
            ssim_rgb(
                &frame_rgb,
                self.last_frame.as_ref().expect("last frame is set"),
                width,
                height,
            )
        } else {
            0.0
        };

        let ocr_text = current_ocr_text.unwrap_or_default();
        let ocr_delta = normalized_ocr_delta(&self.last_ocr_text, &ocr_text);

        let score =
            (PHASH_WEIGHT * hash_delta) + (SSIM_WEIGHT * (1.0 - ssim)) + (OCR_WEIGHT * ocr_delta);

        self.last_frame = Some(frame_rgb);
        self.last_width = width;
        self.last_height = height;
        self.last_phash = Some(current_phash);
        self.last_dhash = Some(current_dhash);
        self.last_ocr_text = ocr_text;

        Ok(score.clamp(0.0, 1.0))
    }
}

#[pyclass]
pub struct RustPrivacyRedactor;

#[pymethods]
impl RustPrivacyRedactor {
    #[new]
    pub fn new() -> Self {
        Self
    }

    pub fn redact(&self, text: String) -> String {
        let mut out = redact_email(&text);
        out = redact_phone(&out);
        out = redact_2fa(&out);
        redact_password(&out)
    }
}

#[pyclass]
pub struct RustFrameBuffer {
    max_frames: usize,
    next_id: u64,
    queue: crossbeam::queue::ArrayQueue<FramePacket>,
}

#[derive(Clone)]
struct FramePacket {
    id: u64,
    width: usize,
    height: usize,
    frame: Vec<u8>,
}

#[pymethods]
impl RustFrameBuffer {
    #[new]
    pub fn new(max_frames: usize) -> PyResult<Self> {
        if max_frames == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "max_frames must be > 0",
            ));
        }
        Ok(Self {
            max_frames,
            next_id: 0,
            queue: crossbeam::queue::ArrayQueue::new(max_frames),
        })
    }

    pub fn add_frame(&mut self, frame_rgb: Vec<u8>, width: usize, height: usize) -> u64 {
        let id = self.next_id;
        self.next_id = self.next_id.saturating_add(1);
        let packet = FramePacket {
            id,
            width,
            height,
            frame: frame_rgb,
        };
        if self.queue.push(packet.clone()).is_err() {
            let _ = self.queue.pop();
            let _ = self.queue.push(packet);
        }
        id
    }

    pub fn len(&self) -> usize {
        self.queue.len()
    }

    pub fn capacity(&self) -> usize {
        self.max_frames
    }

    /// Returns the most recently added frame without fully draining the queue.
    /// Pops all frames to find the tail, re-pushes older ones.
    /// Not safe to call concurrently with add_frame.
    pub fn latest_frame(&self) -> Option<(u64, Vec<u8>, usize, usize)> {
        let mut frames: Vec<FramePacket> = std::iter::from_fn(|| self.queue.pop()).collect();
        if frames.is_empty() {
            return None;
        }

        let latest = frames.pop().expect("non-empty");
        for frame in frames {
            let _ = self.queue.push(frame);
        }

        Some((latest.id, latest.frame, latest.width, latest.height))
    }
}

#[pyclass]
pub struct RustRhythmAnalyzer {
    window_size: usize,
    scores: VecDeque<f32>,
}

#[pymethods]
impl RustRhythmAnalyzer {
    #[new]
    #[pyo3(signature = (window_size=10))]
    pub fn new(window_size: usize) -> PyResult<Self> {
        if window_size == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "window_size must be > 0",
            ));
        }
        Ok(Self {
            window_size,
            scores: VecDeque::with_capacity(window_size),
        })
    }

    pub fn add_score(&mut self, score: f32) {
        if self.scores.len() == self.window_size {
            let _ = self.scores.pop_front();
        }
        self.scores.push_back(score.clamp(0.0, 1.0));
    }

    pub fn classify_mode(&self) -> String {
        if self.scores.is_empty() {
            return "Idle".to_string();
        }
        let avg = self.scores.iter().copied().sum::<f32>() / self.scores.len() as f32;
        if avg > 0.60 {
            "Presentation".to_string()
        } else if avg > 0.20 {
            "Coding".to_string()
        } else {
            "Discussion".to_string()
        }
    }
}

fn phash64(rgb: &[u8], width: usize, height: usize, dct: &dyn Dct2<f32>) -> u64 {
    let small = resize_gray(rgb, width, height, 32, 32);
    let coeffs = dct2_32_with_plan(&small, dct);
    let mut low = [0f32; 64];
    let mut idx = 0usize;
    for y in 0..8 {
        for x in 0..8 {
            low[idx] = coeffs[y * 32 + x];
            idx += 1;
        }
    }
    let mut sorted = low;
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median = sorted[32];

    let mut hash = 0u64;
    for (i, val) in low.iter().enumerate() {
        if *val > median {
            hash |= 1u64 << i;
        }
    }
    hash
}

fn dct2_32_with_plan(input: &[f32], dct: &dyn Dct2<f32>) -> Vec<f32> {
    let mut tmp = vec![0f32; 32 * 32];
    let mut row = vec![0f32; 32];
    for y in 0..32 {
        row.copy_from_slice(&input[y * 32..(y + 1) * 32]);
        dct.process_dct2(&mut row);
        tmp[y * 32..(y + 1) * 32].copy_from_slice(&row);
    }

    let mut out = vec![0f32; 32 * 32];
    let mut col = vec![0f32; 32];
    for x in 0..32 {
        for y in 0..32 {
            col[y] = tmp[y * 32 + x];
        }
        dct.process_dct2(&mut col);
        for y in 0..32 {
            out[y * 32 + x] = col[y];
        }
    }
    out
}

fn dhash64(rgb: &[u8], width: usize, height: usize) -> u64 {
    let small = resize_gray(rgb, width, height, 9, 8);
    let mut hash = 0u64;
    let mut bit = 0u64;
    for y in 0..8 {
        for x in 0..8 {
            let a = small[y * 9 + x];
            let b = small[y * 9 + x + 1];
            if a > b {
                hash |= 1u64 << bit;
            }
            bit += 1;
        }
    }
    hash
}

fn hamming64(a: u64, b: u64) -> f32 {
    (a ^ b).count_ones() as f32 / 64.0
}

fn ssim_rgb(a: &[u8], b: &[u8], width: usize, height: usize) -> f32 {
    let n = (width * height) as f32;
    if n <= 1.0 {
        return 1.0;
    }

    let gray_a = rgb_to_gray(a);
    let gray_b = rgb_to_gray(b);

    let mut sum_a = 0.0f32;
    let mut sum_b = 0.0f32;
    let mut sum_a2 = 0.0f32;
    let mut sum_b2 = 0.0f32;
    let mut sum_ab = 0.0f32;

    for (&ga, &gb) in gray_a.iter().zip(gray_b.iter()) {
        sum_a += ga;
        sum_b += gb;
        sum_a2 += ga * ga;
        sum_b2 += gb * gb;
        sum_ab += ga * gb;
    }

    let mu_a = sum_a / n;
    let mu_b = sum_b / n;
    let var_a = (sum_a2 / n) - (mu_a * mu_a);
    let var_b = (sum_b2 / n) - (mu_b * mu_b);
    let cov_ab = (sum_ab / n) - (mu_a * mu_b);

    let c1 = 6.5025;
    let c2 = 58.5225;
    let numerator = (2.0 * mu_a * mu_b + c1) * (2.0 * cov_ab + c2);
    let denominator = (mu_a * mu_a + mu_b * mu_b + c1) * (var_a + var_b + c2);

    if denominator.abs() < f32::EPSILON {
        1.0
    } else {
        (numerator / denominator).clamp(0.0, 1.0)
    }
}

fn normalized_ocr_delta(prev: &str, current: &str) -> f32 {
    if prev.is_empty() && current.is_empty() {
        return 0.0;
    }
    if prev == current {
        return 0.0;
    }
    let max_len = prev.chars().count().max(current.chars().count()) as f32;
    if max_len == 0.0 {
        return 0.0;
    }
    strsim::levenshtein(prev, current) as f32 / max_len
}

fn resize_gray(rgb: &[u8], src_w: usize, src_h: usize, dst_w: usize, dst_h: usize) -> Vec<f32> {
    let mut out = vec![0f32; dst_w * dst_h];
    let sx = src_w as f32 / dst_w as f32;
    let sy = src_h as f32 / dst_h as f32;

    for y in 0..dst_h {
        let src_y = ((y as f32 * sy).floor() as usize).min(src_h.saturating_sub(1));
        for x in 0..dst_w {
            let src_x = ((x as f32 * sx).floor() as usize).min(src_w.saturating_sub(1));
            let idx = (src_y * src_w + src_x) * 3;
            out[y * dst_w + x] = rgb_to_gray_pixel(rgb[idx], rgb[idx + 1], rgb[idx + 2]);
        }
    }

    out
}

fn rgb_to_gray(rgb: &[u8]) -> Vec<f32> {
    let mut out = vec![0f32; rgb.len() / 3];
    for (dst, px) in out.iter_mut().zip(rgb.chunks_exact(3)) {
        *dst = rgb_to_gray_pixel(px[0], px[1], px[2]);
    }
    out
}

#[inline]
fn rgb_to_gray_pixel(r: u8, g: u8, b: u8) -> f32 {
    0.299 * r as f32 + 0.587 * g as f32 + 0.114 * b as f32
}

fn redact_email(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut token = String::new();

    for ch in text.chars() {
        if ch.is_whitespace() {
            if token.contains('@') && token.contains('.') {
                out.push_str("[REDACTED_EMAIL]");
            } else {
                out.push_str(&token);
            }
            token.clear();
            out.push(ch);
        } else {
            token.push(ch);
        }
    }

    if !token.is_empty() {
        if token.contains('@') && token.contains('.') {
            out.push_str("[REDACTED_EMAIL]");
        } else {
            out.push_str(&token);
        }
    }

    out
}

fn redact_phone(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut digits = 0usize;
    let mut token = String::new();

    let flush = |token: &mut String, digits: usize, out: &mut String| {
        if digits >= 10 {
            out.push_str("[REDACTED_PHONE]");
        } else {
            out.push_str(token);
        }
        token.clear();
    };

    for ch in text.chars() {
        if ch.is_ascii_digit() || ch == '+' || ch == '-' || ch == '.' || ch == '(' || ch == ')' {
            if ch.is_ascii_digit() {
                digits += 1;
            }
            token.push(ch);
        } else {
            if !token.is_empty() {
                flush(&mut token, digits, &mut out);
                digits = 0;
            }
            out.push(ch);
        }
    }

    if !token.is_empty() {
        flush(&mut token, digits, &mut out);
    }

    out
}

fn redact_2fa(text: &str) -> String {
    let lower = text.to_ascii_lowercase();
    if !(lower.contains("2fa")
        || lower.contains("otp")
        || lower.contains("verification")
        || lower.contains("code"))
    {
        return text.to_string();
    }

    let mut out = String::with_capacity(text.len());
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if chars[i].is_ascii_digit() {
            let start = i;
            while i < chars.len() && chars[i].is_ascii_digit() {
                i += 1;
            }
            let len = i - start;
            if len == 6 {
                out.push_str("[REDACTED_2FA]");
            } else {
                for ch in &chars[start..i] {
                    out.push(*ch);
                }
            }
            continue;
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

fn redact_password(text: &str) -> String {
    let mut out = String::new();
    for line in text.lines() {
        let lower = line.to_ascii_lowercase();
        if lower.contains("password") || lower.contains("passwd") || lower.contains("secret") {
            if let Some((prefix, _)) = line.split_once(':') {
                out.push_str(prefix);
                out.push_str(": [REDACTED_PASSWORD]\n");
                continue;
            }
            if let Some((prefix, _)) = line.split_once('=') {
                out.push_str(prefix);
                out.push_str("= [REDACTED_PASSWORD]\n");
                continue;
            }
        }
        out.push_str(line);
        out.push('\n');
    }
    out.trim_end_matches('\n').to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame(width: usize, height: usize, value: u8) -> Vec<u8> {
        vec![value; width * height * 3]
    }

    #[test]
    fn scene_detector_first_and_identical_frame() {
        let mut detector = RustSceneChangeDetector::new();
        let first = detector
            .calculate_scene_score(frame(32, 32, 0), 32, 32, Some(String::new()))
            .expect("first score should work");
        assert_eq!(first, 1.0);

        let second = detector
            .calculate_scene_score(frame(32, 32, 0), 32, 32, Some(String::new()))
            .expect("second score should work");
        assert!(
            second <= 0.01,
            "expected near zero for identical frame, got {second}"
        );
    }

    #[test]
    fn scene_detector_detects_change() {
        let mut detector = RustSceneChangeDetector::new();
        let _ = detector.calculate_scene_score(frame(32, 32, 0), 32, 32, Some("abc".to_string()));
        let score = detector
            .calculate_scene_score(frame(32, 32, 255), 32, 32, Some("xyz".to_string()))
            .expect("changed frame should score");
        assert!(score > 0.20, "expected change score > 0.20, got {score}");
    }

    #[test]
    fn scene_detector_handles_zero_sized_frame() {
        let mut detector = RustSceneChangeDetector::new();
        let score = detector
            .calculate_scene_score(Vec::new(), 0, 0, Some(String::new()))
            .expect("zero-sized frame must not panic");
        assert_eq!(score, 0.0);
    }

    #[test]
    fn latest_frame_does_not_drain_entire_queue() {
        let mut buffer = RustFrameBuffer::new(4).expect("buffer init");
        let _id0 = buffer.add_frame(frame(4, 4, 1), 4, 4);
        let _id1 = buffer.add_frame(frame(4, 4, 2), 4, 4);
        let id2 = buffer.add_frame(frame(4, 4, 3), 4, 4);

        let result = buffer.latest_frame();
        let (returned_id, returned_frame, _, _) = result.expect("must return a frame");
        assert_eq!(returned_id, id2, "must return last frame id");
        assert!(
            returned_frame.iter().all(|&b| b == 3),
            "must return last frame data"
        );
        assert_eq!(buffer.len(), 2, "older frames must remain in queue");
    }

    #[test]
    fn privacy_redaction_masks_sensitive_values() {
        let redactor = RustPrivacyRedactor::new();
        let redacted = redactor.redact(
            "email me at test@example.com and call +1-123-456-7890 password: abc otp code 123456"
                .to_string(),
        );
        assert!(redacted.contains("[REDACTED_EMAIL]"));
        assert!(redacted.contains("[REDACTED_PHONE]"));
        assert!(redacted.contains("[REDACTED_PASSWORD]"));
        assert!(redacted.contains("[REDACTED_2FA]"));
    }

    #[test]
    fn privacy_redaction_does_not_mask_arbitrary_six_digits_without_context() {
        let redactor = RustPrivacyRedactor::new();
        let text = "invoice id 123456 should stay visible".to_string();
        let redacted = redactor.redact(text.clone());
        assert_eq!(redacted, text);
    }
}
