import wave
import struct
import math
import sys
import os
from datetime import datetime

from mk import ensure_loaded, get_hooks
ensure_loaded()

FREQ_SYM = {1000:0,1200:1,1400:2,1600:3,1800:4,2000:5,2200:6,2400:7}
FREQ_SYNC = 3400

SYM_DUR = 0.08
SYNC_DUR = 0.5
START_DUR = 0.1
SEP_DUR = 0.04

SAMPLE_RATE = 44100

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def goertzel(data, target):
    n = len(data)
    if n == 0:
        return 0
    k = int(0.5 + n * target / SAMPLE_RATE)
    omega = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(omega)
    s1 = s2 = 0.0
    for s in data:
        s0 = s + coeff * s1 - s2
        s2, s1 = s1, s0
    return s2*s2 + s1*s1 - coeff*s1*s2

def detect_symbol(window, fallback=None):
    best_sym, best_power = None, 0
    powers = {}
    for freq, sym in FREQ_SYM.items():
        power = goertzel(window, freq)
        powers[sym] = power
        if power > best_power:
            best_power, best_sym = power, sym
    avg_power = sum(powers.values()) / len(powers) if powers else 0
    if avg_power < 1.0:
        return fallback
    if best_power > avg_power * 2.5:
        return best_sym
    return fallback

def find_sync(samples):
    win = int(SAMPLE_RATE * 0.1)
    step = int(SAMPLE_RATE * 0.05)
    max_power = 0
    best_pos = -1
    powers = []

    for pos in range(0, len(samples) - win, step):
        power = goertzel(samples[pos:pos+win], FREQ_SYNC)
        powers.append(power)
        if power > max_power:
            max_power = power
            best_pos = pos

    if not powers:
        return -1

    avg_power = sum(powers) / len(powers)
    if max_power > avg_power * 4:
        return best_pos + int(SAMPLE_RATE * SYNC_DUR)
    return -1

def decode_byte(s1, s2, s3):
    high = (s1 & 0x07) << 5
    mid = (s2 & 0x07) << 2
    low = s3 & 0x03
    return high | mid | low

def decode(samples):
    sync_end = find_sync(samples)
    if sync_end == -1:
        return None

    data_start = sync_end + int(SAMPLE_RATE * (START_DUR + SEP_DUR))
    sym_len = int(SAMPLE_RATE * SYM_DUR)
    pos = data_start
    raw = []
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5

    while pos + sym_len * 3 < len(samples):
        s1 = detect_symbol(samples[pos:pos+sym_len])
        s2 = detect_symbol(samples[pos+sym_len:pos+2*sym_len])
        s3 = detect_symbol(samples[pos+2*sym_len:pos+3*sym_len])

        if s1 is None or s2 is None or s3 is None:
            consecutive_errors += 1
            if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
                log("连续解码错误过多，终止解码")
                break
            pos += sym_len * 3 + int(SAMPLE_RATE * SEP_DUR)
            continue

        consecutive_errors = 0
        b = decode_byte(s1, s2, s3)
        raw.append(b)
        pos += sym_len * 3 + int(SAMPLE_RATE * SEP_DUR)

    try:
        return bytes(raw).decode('utf-8')
    except UnicodeDecodeError as e:
        log(f"UTF-8 解码失败: {e}")
        return None

def decode_file(path):
    if not os.path.exists(path):
        log("文件不存在")
        return None

    try:
        w = wave.open(path, 'rb')
    except Exception as e:
        log(f"无法打开 WAV 文件: {e}")
        return None

    if w.getnchannels() != 1 or w.getsampwidth() != 2:
        log("仅支持 16-bit 单声道 PCM WAV")
        w.close()
        return None

    frames = w.readframes(w.getnframes())
    w.close()
    samples = []
    for i in range(0, len(frames), 2):
        samples.append(struct.unpack('<h', frames[i:i+2])[0])

    for hook in get_hooks('decode_pre'):
        samples = hook(samples)

    cmd = decode(samples)

    for hook in get_hooks('decode_post'):
        if cmd:
            cmd = hook(cmd)

    if cmd:
        print(f"[OK] {cmd}")
    else:
        print("[FAIL] 解码失败")
    return cmd

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "cmd.wav"
    decode_file(path)

if __name__ == "__main__":
    main()