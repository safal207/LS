from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import platform
import shutil
import subprocess
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GPUInfo:
    name: str | None
    vram_total_mb: float | None
    vram_free_mb: float | None
    cuda: bool
    cuda_version: str | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vramtotalmb": self.vram_total_mb,
            "vramfreemb": self.vram_free_mb,
            "cuda": self.cuda,
            "cudaversion": self.cuda_version,
        }


@dataclass(frozen=True)
class TorchInfo:
    cuda: bool
    mps: bool
    fp16: bool
    bf16: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cuda": self.cuda,
            "mps": self.mps,
            "fp16": self.fp16,
            "bf16": self.bf16,
        }


@dataclass(frozen=True)
class HardwareProfile:
    cpu_cores: int
    cpu_freq_ghz: float | None
    cpu_arch: str
    ram_total_mb: float
    ram_available_mb: float
    ram_used_mb: float
    gpu: GPUInfo | None
    torch: TorchInfo
    libraries: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "cpu_cores": self.cpu_cores,
            "cpu_freq": self.cpu_freq_ghz,
            "cpu_arch": self.cpu_arch,
            "ramtotalmb": self.ram_total_mb,
            "ramavailablemb": self.ram_available_mb,
            "ramusedmb": self.ram_used_mb,
            "torch": self.torch.to_dict(),
            "libraries": dict(self.libraries),
        }
        if self.gpu is not None:
            payload["gpu"] = self.gpu.to_dict()
        return payload


class HardwareProfiler:
    def __init__(self) -> None:
        self._library_targets = {
            "transformers": "transformers",
            "faster_whisper": "faster_whisper",
            "torch": "torch",
            "ollama": "ollama",
        }

    def collect(self) -> HardwareProfile:
        psutil = _psutil()
        memory = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()
        cpu_freq_ghz = None
        if cpu_freq and cpu_freq.current:
            cpu_freq_ghz = round(cpu_freq.current / 1000.0, 2)
        cpu_arch = platform.machine() or platform.processor() or "unknown"

        torch_info = self._collect_torch_info()
        gpu_info = self._collect_gpu_info(torch_info.cuda)
        libraries = self._collect_libraries()

        return HardwareProfile(
            cpu_cores=psutil.cpu_count(logical=True) or 0,
            cpu_freq_ghz=cpu_freq_ghz,
            cpu_arch=cpu_arch,
            ram_total_mb=round(memory.total / (1024 * 1024), 2),
            ram_available_mb=round(memory.available / (1024 * 1024), 2),
            ram_used_mb=round(memory.used / (1024 * 1024), 2),
            gpu=gpu_info,
            torch=torch_info,
            libraries=libraries,
        )

    def _collect_libraries(self) -> Dict[str, bool]:
        return {
            name: importlib.util.find_spec(module) is not None
            for name, module in self._library_targets.items()
        }

    def _collect_torch_info(self) -> TorchInfo:
        torch_spec = importlib.util.find_spec("torch")
        if torch_spec is None:
            return TorchInfo(cuda=False, mps=False, fp16=False, bf16=False)
        torch = importlib.import_module("torch")
        cuda_available = torch.cuda.is_available()
        mps_available = bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()
        fp16_available = cuda_available or mps_available
        bf16_supported_fn = getattr(torch.cuda, "is_bf16_supported", None)
        bf16_available = bool(bf16_supported_fn()) if cuda_available and bf16_supported_fn else False
        return TorchInfo(
            cuda=cuda_available,
            mps=mps_available,
            fp16=fp16_available,
            bf16=bf16_available,
        )

    def _collect_gpu_info(self, torch_cuda_available: bool) -> Optional[GPUInfo]:
        if torch_cuda_available:
            torch = importlib.import_module("torch")
            name = torch.cuda.get_device_name(0)
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            cuda_version = torch.version.cuda
            return GPUInfo(
                name=name,
                vram_total_mb=round(total_bytes / (1024 * 1024), 2),
                vram_free_mb=round(free_bytes / (1024 * 1024), 2),
                cuda=True,
                cuda_version=cuda_version,
            )

        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return None
        query = [
            nvidia_smi,
            "--query-gpu=name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
        try:
            output = subprocess.check_output(query, text=True).strip()
        except subprocess.CalledProcessError:
            return None
        if not output:
            return None
        parts = [part.strip() for part in output.split(",")]
        if len(parts) < 3:
            return None
        name = parts[0]
        total = float(parts[1])
        free = float(parts[2])
        cuda_version = parts[3] if len(parts) > 3 else None
        return GPUInfo(
            name=name,
            vram_total_mb=total,
            vram_free_mb=free,
            cuda=True,
            cuda_version=cuda_version,
        )


def _psutil():
    if importlib.util.find_spec("psutil") is None:
        raise RuntimeError("psutil is required for hardware profiling.")
    return importlib.import_module("psutil")
