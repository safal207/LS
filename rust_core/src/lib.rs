use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Debug, thiserror::Error)]
pub enum AudioError {
    #[error("Audio device error: {0}")]
    DeviceError(String),
    #[error("Buffer overflow")]
    BufferOverflow,
    #[error("Invalid audio format")]
    InvalidFormat,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioConfig {
    pub sample_rate: u32,
    pub channels: u16,
    pub buffer_duration_ms: u32,
    pub vad_threshold: f32,  // 0.0 to 1.0
}

impl Default for AudioConfig {
    fn default() -> Self {
        Self {
            sample_rate: 16000,
            channels: 1,
            buffer_duration_ms: 50,  // 50ms chunks
            vad_threshold: 0.01,     // Energy threshold
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioChunk {
    pub samples: Vec<f32>,
    pub timestamp: u64,
    pub is_voice_active: bool,
}

pub struct AudioProcessor {
    config: AudioConfig,
    ring_buffer: Arc<Mutex<ringbuf::HeapRb<AudioChunk>>>,
    device: Option<cpal::Device>,
}

impl AudioProcessor {
    pub fn new(config: AudioConfig) -> Result<Self, AudioError> {
        let buffer_size = (config.sample_rate * config.buffer_duration_ms / 1000) as usize;
        let ring_buffer = Arc::new(Mutex::new(ringbuf::HeapRb::new(buffer_size * 10))); // 10 chunks buffer
        
        Ok(Self {
            config,
            ring_buffer,
            device: None,
        })
    }

    pub async fn initialize_device(&mut self) -> Result<(), AudioError> {
        let host = cpal::default_host();
        let device = host.default_input_device()
            .ok_or(AudioError::DeviceError("No input device found".to_string()))?;
        
        self.device = Some(device);
        Ok(())
    }

    pub fn calculate_rms(samples: &[f32]) -> f32 {
        let sum_squares: f32 = samples.iter().map(|&x| x * x).sum();
        (sum_squares / samples.len() as f32).sqrt()
    }

    pub fn is_voice_active(&self, samples: &[f32]) -> bool {
        let rms = Self::calculate_rms(samples);
        rms > self.config.vad_threshold
    }

    pub async fn process_chunk(&self, samples: Vec<f32>) -> Result<AudioChunk, AudioError> {
        let is_voice = self.is_voice_active(&samples);
        
        let chunk = AudioChunk {
            samples,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64,
            is_voice_active: is_voice,
        };

        // Store in ring buffer
        {
            let mut buffer = self.ring_buffer.lock().await;
            buffer.push(chunk.clone()).map_err(|_| AudioError::BufferOverflow)?;
        }

        Ok(chunk)
    }

    pub async fn get_latest_chunks(&self, count: usize) -> Vec<AudioChunk> {
        let buffer = self.ring_buffer.lock().await;
        buffer.iter().take(count).cloned().collect()
    }

    pub async fn clear_buffer(&self) {
        let mut buffer = self.ring_buffer.lock().await;
        buffer.clear();
    }
}

// Memory-efficient audio utilities
pub mod utils {
    pub fn convert_i16_to_f32(input: &[i16]) -> Vec<f32> {
        input.iter().map(|&x| x as f32 / 32768.0).collect()
    }

    pub fn convert_f32_to_i16(input: &[f32]) -> Vec<i16> {
        input.iter().map(|&x| (x * 32767.0) as i16).collect()
    }

    pub fn apply_volume_normalization(samples: &mut [f32], target_rms: f32) {
        let current_rms = super::AudioProcessor::calculate_rms(samples);
        if current_rms > 0.0 {
            let scale = target_rms / current_rms;
            for sample in samples.iter_mut() {
                *sample *= scale;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rms_calculation() {
        let samples = vec![1.0, -1.0, 1.0, -1.0];
        let rms = AudioProcessor::calculate_rms(&samples);
        assert!((rms - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_voice_detection() {
        let config = AudioConfig {
            vad_threshold: 0.1,
            ..Default::default()
        };
        let processor = AudioProcessor::new(config).unwrap();
        
        // Silence
        let silence = vec![0.0; 100];
        assert!(!processor.is_voice_active(&silence));
        
        // Voice-like signal
        let voice = vec![0.15; 100];
        assert!(processor.is_voice_active(&voice));
    }

    #[tokio::test]
    async fn test_buffer_operations() {
        let processor = AudioProcessor::new(Default::default()).unwrap();
        let chunk = vec![0.5; 100];
        
        let result = processor.process_chunk(chunk).await;
        assert!(result.is_ok());
        
        let chunks = processor.get_latest_chunks(5).await;
        assert_eq!(chunks.len(), 1);
    }
}