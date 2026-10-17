"""Measure the actual ML environment without downloading weights or changing drivers."""
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import torch

root = Path(__file__).resolve().parents[2]
report = {
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'os': platform.system(), 'architecture': platform.machine(), 'python': platform.python_version(),
    'laya': importlib.metadata.version('laya'), 'torch': torch.__version__,
    'torch_cuda': torch.version.cuda, 'cuda_available': torch.cuda.is_available(),
    'checkpoint_loaded': False, 'training_run': False,
}
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    report['gpu'] = props.name
    report['total_vram_mib'] = props.total_memory // (1024 ** 2)
    free, total = torch.cuda.mem_get_info()
    report['free_vram_mib_at_probe'] = free // (1024 ** 2)
    result = (torch.ones((32, 32), device='cuda') @ torch.ones((32, 32), device='cuda')).sum().item()
    report['cuda_tensor_probe'] = 'PASS' if result == 32768 else 'FAIL'
report['nvidia_smi'] = subprocess.check_output([
    'nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'], text=True).strip()
(root / 'ml/environment.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
