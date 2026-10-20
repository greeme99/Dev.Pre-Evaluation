"""Hardware detection and profiling (FN-008, MOD-001)."""

import os
import shutil
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HardwareProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    has_cuda: bool
    execution_provider: Literal["cpu", "cuda"]
    ram_mb: int
    vram_mb: int = 0
    device_name: str | None = None


class HardwareDetector:
    def detect(self) -> HardwareProfile:
        ram_mb = self._detect_system_ram_mb()

        # Check CUDA availability
        has_cuda = False
        vram_mb = 0
        device_name: str | None = None

        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                has_cuda = True
                props = torch.cuda.get_device_properties(0)
                vram_mb = int(props.total_memory // (1024 * 1024))
                device_name = getattr(props, "name", "NVIDIA CUDA Device")
        except Exception:  # noqa: S110
            # PyTorch not installed or no CUDA runtime
            pass

        # If not detected via torch, check nvidia-smi
        if not has_cuda and shutil.which("nvidia-smi") is not None:
            # Fallback or manual detection if needed
            pass

        return HardwareProfile(
            has_cuda=has_cuda,
            execution_provider="cuda" if has_cuda else "cpu",
            ram_mb=ram_mb,
            vram_mb=vram_mb,
            device_name=device_name,
        )

    def _detect_system_ram_mb(self) -> int:
        try:
            # Linux / macOS
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int((pages * page_size) // (1024 * 1024))
        except Exception:
            return 8192  # Default 8 GB fallback
