use std::cmp::{Ordering, Reverse};
use std::collections::{BinaryHeap, HashSet, VecDeque};
use std::sync::Arc;
use tokio::sync::Notify;

#[derive(Eq, PartialEq)]
struct PrioritizedMessage {
    priority: i32,
    sequence: u64,
    message: String,
}

impl Ord for PrioritizedMessage {
    fn cmp(&self, other: &Self) -> Ordering {
        self.priority
            .cmp(&other.priority)
            .then_with(|| other.sequence.cmp(&self.sequence))
    }
}

impl PartialOrd for PrioritizedMessage {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

pub struct AsyncWeb4RttBinding {
    connected: bool,
    queue: VecDeque<String>,
    priority_queue: BinaryHeap<PrioritizedMessage>,
    priority_oldest: BinaryHeap<Reverse<u64>>,
    live_sequences: HashSet<u64>,
    next_sequence: u64,
    notify: Arc<Notify>,
}

impl AsyncWeb4RttBinding {
    pub fn new() -> Self {
        Self {
            connected: true,
            queue: VecDeque::new(),
            priority_queue: BinaryHeap::new(),
            priority_oldest: BinaryHeap::new(),
            live_sequences: HashSet::new(),
            next_sequence: 0,
            notify: Arc::new(Notify::new()),
        }
    }

    pub async fn send_async(&mut self, message: String, priority: Option<i32>) {
        if let Some(priority_value) = priority {
            self.next_sequence = self.next_sequence.wrapping_add(1);
            self.priority_queue.push(PrioritizedMessage {
                priority: priority_value,
                sequence: self.next_sequence,
                message,
            });
            self.priority_oldest.push(Reverse(self.next_sequence));
            self.live_sequences.insert(self.next_sequence);
        } else {
            self.queue.push_back(message);
        }
        self.notify.notify_waiters();
    }

    pub async fn receive_async(&mut self) -> Option<String> {
        if !self.connected {
            return None;
        }
        while let Some(peeked) = self.priority_queue.peek() {
            if self.live_sequences.contains(&peeked.sequence) {
                break;
            }
            let _ = self.priority_queue.pop();
        }

        if let Some(pm) = self.priority_queue.pop() {
            self.live_sequences.remove(&pm.sequence);
            return Some(pm.message);
        }

        self.queue.pop_front()
    }
}
