import wave
import struct
import math
import sys
import os
from datetime import datetime

from mk import ensure_loaded, get_hooks
ensure_loaded()

FREQ_SYM = {0:1000,1:1200,2:1400,3:1600,4:1800,5:2000,6:2200,7:2400}
FREQ_SYNC = 3400

SYM_DUR = 0.08
SYNC_DUR = 0.5
START_DUR = 0.1
SEP_DUR = 0.04

SAMPLE_RATE = 44100
VOLUME = 28000   # 留出安全余量，防止叠加信号溢出

def clamp(val, min_val, max_val):
    return max(min_val, min(max_val, val))

def gen_tone(freq, sec):
    n = int(SAMPLE_RATE * sec)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        val = int(VOLUME * math.sin(2 * math.pi * freq * t))
        samples.append(clamp(val, -32768, 32767))
    return samples

def gen_silence(sec):
    return [0] * int(SAMPLE_RATE * sec)

def encode_symbol(val):
    return gen_tone(FREQ_SYM[val], SYM_DUR)

def encode_byte(byte):
    b1 = (byte >> 5) & 0x07
    b2 = (byte >> 2) & 0x07
    b3 = ((byte & 0x03) << 1) | ((byte >> 4) & 1)   # 完全对称
    samples = encode_symbol(b1) + encode_symbol(b2) + encode_symbol(b3)
    samples += gen_silence(SEP_DUR)
    return samples

def encode(cmd):
    for hook in get_hooks('encode_pre'):
        cmd = hook['func'](cmd)
    
    samples = []
    samples += gen_tone(FREQ_SYNC, SYNC_DUR)
    samples += gen_tone(FREQ_SYNC, START_DUR)
    samples += gen_silence(SEP_DUR)
    for b in cmd.encode('utf-8'):
        samples += encode_byte(b)
    
    for hook in get_hooks('encode_post'):
        samples = hook['func'](samples)
    return samples

def print_help():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    音频管理通道协议 - 编码器 v1.2                            ║
╠════════════════════════════════════════════════════════════════════════════╣ 
║ 用法: python encoder.py "指令"                                              ║
║ 输出: cmd.wav                                                              ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    
    cmd = sys.argv[1]
    samples = encode(cmd)
    w = wave.open('cmd.wav', 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SAMPLE_RATE)
    w.writeframes(b''.join(struct.pack('<h', s) for s in samples))
    w.close()
    print(f"[OK] cmd.wav ({len(samples)/SAMPLE_RATE:.1f}秒)")

if __name__ == "__main__":
    main()