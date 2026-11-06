"""Cached local hardware observations; temperature alone never sets a price."""
import csv
import hashlib
import io
import json
import subprocess
import threading
import time

FIELDS = ('uuid','name','temperature.gpu','utilization.gpu','memory.used','memory.total','power.draw',
          'clocks.sm','clocks.max.sm','clocks_event_reasons.sw_thermal_slowdown',
          'clocks_event_reasons.hw_thermal_slowdown')
_lock = threading.Lock()
_sample = None
_sampled_at = 0


def number(value):
    try:
        result=float(value)
        return result if result>=0 and result<float('inf') else None
    except ValueError:return None


def parse(raw, observed_at):
    rows=list(csv.reader(io.StringIO(raw)))
    if not rows or len(rows[0])!=len(FIELDS):raise ValueError('Invalid GPU sample')
    values=[v.strip() for v in rows[0]]
    active=lambda v: True if v.lower()=='active' else False if v.lower()=='not active' else None
    thermal=[active(values[9]),active(values[10])]
    result={'label':'MEASURED','source':'LOCAL_NVIDIA_SMI','device_index':0,'gpu_uuid':values[0],
            'gpu_name':values[1],'observed_at':observed_at,'temperature_c':number(values[2]),
            'gpu_utilization_percent':number(values[3]),'vram_used_mib':number(values[4]),
            'vram_total_mib':number(values[5]),'power_w':number(values[6]),
            'sm_clock_mhz':number(values[7]),'max_sm_clock_mhz':number(values[8]),
            'thermal_throttling_active':True if True in thermal else False if all(v is False for v in thermal) else None,
            'throughput_tokens_per_second':None,'throughput_status':'UNMEASURED',
            'pricing_coefficients_status':'UNMEASURED_NO_CAPACITY_MARKUP',
            'temperature_alone_changes_price':False,'remote_hardware_attestation':False}
    result['sample_id']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()[:24]
    return result


def sample(now=None, runner=subprocess.run):
    global _sample,_sampled_at
    now=time.time() if now is None else now
    with _lock:
        if _sample is not None and 0<=now-_sampled_at<5:return dict(_sample)
        try:
            process=runner(['nvidia-smi','--query-gpu='+','.join(FIELDS),'--format=csv,noheader,nounits'],
                           capture_output=True,text=True,timeout=3)
            if process.returncode:raise ValueError('GPU sample unavailable')
            result=parse(process.stdout,now)
        except (OSError,ValueError,subprocess.SubprocessError):
            result={'label':'BLOCKED','observed_at':now,'reason':'Local GPU telemetry unavailable',
                    'sample_id':None,'thermal_throttling_active':None,'temperature_alone_changes_price':False}
        _sample,_sampled_at=result,now
        return dict(result)
