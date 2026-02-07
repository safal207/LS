#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

struct syscall_counts {
    __u64 read;
    __u64 write;
    __u64 open;
    __u64 close;
    __u64 ioctl;
};

struct perf_snapshot {
    __u64 cycles;
    __u64 instructions;
    __u64 cache_misses;
    __u64 branch_mispredicts;
};

struct kacl_event {
    __u64 timestamp;
    struct syscall_counts syscalls;
    __u64 context_switches;
    __u64 page_faults;
    __u64 iowait_ms;
    struct perf_snapshot perf;
};

struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
} events SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct kacl_event);
} scratch SEC(".maps");

SEC("tracepoint/syscalls/sys_enter_read")
int kacl_enter_read(struct trace_event_raw_sys_enter *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->syscalls.read += 1;
    return 0;
}

SEC("tracepoint/syscalls/sys_enter_write")
int kacl_enter_write(struct trace_event_raw_sys_enter *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->syscalls.write += 1;
    return 0;
}

SEC("tracepoint/syscalls/sys_enter_openat")
int kacl_enter_open(struct trace_event_raw_sys_enter *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->syscalls.open += 1;
    return 0;
}

SEC("tracepoint/syscalls/sys_enter_close")
int kacl_enter_close(struct trace_event_raw_sys_enter *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->syscalls.close += 1;
    return 0;
}

SEC("tracepoint/syscalls/sys_enter_ioctl")
int kacl_enter_ioctl(struct trace_event_raw_sys_enter *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->syscalls.ioctl += 1;
    return 0;
}

SEC("tracepoint/sched/sched_switch")
int kacl_sched_switch(struct trace_event_raw_sched_switch *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->context_switches += 1;
    return 0;
}

SEC("tracepoint/exceptions/page_fault_user")
int kacl_page_fault(struct trace_event_raw_page_fault_user *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->page_faults += 1;
    return 0;
}

SEC("tracepoint/timer/hrtimer_start")
int kacl_emit(struct trace_event_raw_hrtimer_start *ctx) {
    __u32 key = 0;
    struct kacl_event *event = bpf_map_lookup_elem(&scratch, &key);
    if (!event) {
        return 0;
    }
    event->timestamp = bpf_ktime_get_ns();
    bpf_perf_event_output(ctx, &events, BPF_F_CURRENT_CPU, event, sizeof(*event));
    __builtin_memset(event, 0, sizeof(*event));
    return 0;
}

char LICENSE[] SEC("license") = "Dual MIT/GPL";
