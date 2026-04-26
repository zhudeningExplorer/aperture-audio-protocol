import wave
import struct
import math
import sys
import os
import re
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
VOLUME = 28000

# ========== 白名单定义 ==========
BUILTIN_COMMANDS = {
    # 系统指令
    "NOP", "STOP", "STATUS", "PING", "REBOOT", "SHUTDOWN",
    "RESET", "LOCK", "UNLOCK", "SLEEP", "WAKE",
    # 运动指令
    "MOVE", "TURN", "SPEED", "STOP_MOVE", "HOME",
    # 外设指令
    "SCREEN_ON", "SCREEN_OFF", "SCREEN_COLOR", "LED_ON", "LED_OFF",
    "LED_COLOR", "CAMERA_ON", "CAMERA_OFF", "VOLUME", "MUTE", "UNMUTE",
    # 媒体指令
    "PLAY", "PAUSE", "RESUME", "STOP", "NEXT", "PREV", "REPEAT", "SHUFFLE"
}

# 指令正则模式
COMMAND_PATTERNS = {
    "NOP": r"^NOP$",
    "STOP": r"^STOP$",
    "STATUS": r"^STATUS$",
    "PING": r"^PING$",
    "REBOOT": r"^REBOOT$",
    "SHUTDOWN": r"^SHUTDOWN$",
    "RESET": r"^RESET$",
    "LOCK": r"^LOCK$",
    "UNLOCK": r"^UNLOCK$",
    "SLEEP": r"^SLEEP$",
    "WAKE": r"^WAKE$",
    "MOVE": r"^MOVE\s+([1-9][0-9]{0,3}|0)$",      # 1-9999
    "TURN": r"^TURN\s+([0-9]|[1-9][0-9]{1,2}|[1-3][0-9]{3}|3600)$",  # 0-3600
    "SPEED": r"^SPEED\s+([0-9]|[1-9][0-9]{1,2}|255)$",  # 0-255
    "STOP_MOVE": r"^STOP_MOVE$",
    "HOME": r"^HOME$",
    "SCREEN_ON": r"^SCREEN_ON$",
    "SCREEN_OFF": r"^SCREEN_OFF$",
    "SCREEN_COLOR": r"^SCREEN_COLOR\s+([0-9]|[1-9][0-9]{1,2}|255)\s+([0-9]|[1-9][0-9]{1,2}|255)\s+([0-9]|[1-9][0-9]{1,2}|255)$",
    "LED_ON": r"^LED_ON$",
    "LED_OFF": r"^LED_OFF$",
    "LED_COLOR": r"^LED_COLOR\s+([0-9]|[1-9][0-9]{1,2}|255)\s+([0-9]|[1-9][0-9]{1,2}|255)\s+([0-9]|[1-9][0-9]{1,2}|255)$",
    "CAMERA_ON": r"^CAMERA_ON$",
    "CAMERA_OFF": r"^CAMERA_OFF$",
    "VOLUME": r"^VOLUME\s+([0-9]|[1-9][0-9]{1,2}|255)$",
    "MUTE": r"^MUTE$",
    "UNMUTE": r"^UNMUTE$",
    "PLAY": r"^PLAY$",
    "PAUSE": r"^PAUSE$",
    "RESUME": r"^RESUME$",
    "STOP": r"^STOP$",
    "NEXT": r"^NEXT$",
    "PREV": r"^PREV$",
    "REPEAT": r"^REPEAT\s+[012]$",
    "SHUFFLE": r"^SHUFFLE\s+[01]$",
}

# 扩展指令集（从模块加载）
EXTRA_COMMANDS = {}
EXTRA_PATTERNS = {}

def register_command(cmd_name, pattern):
    """供扩展模块调用的注册函数"""
    EXTRA_COMMANDS[cmd_name] = True
    EXTRA_PATTERNS[cmd_name] = pattern

def validate_command(cmd_str):
    """验证完整指令字符串"""
    # 先执行扩展模块的预验证钩子
    for hook in get_hooks('validate_pre'):
        result = hook['func'](cmd_str)
        if result is not None:
            return result
    
    # 分号分隔多条指令
    parts = [p.strip() for p in cmd_str.split(';') if p.strip()]
    if not parts:
        return False, "指令为空"
    
    for part in parts:
        # 检查是否在白名单或扩展集中
        cmd_name = part.split()[0] if ' ' in part else part
        if cmd_name not in BUILTIN_COMMANDS and cmd_name not in EXTRA_COMMANDS:
            return False, f"未知指令: {cmd_name}"
        
        # 检查格式
        pattern = COMMAND_PATTERNS.get(cmd_name) or EXTRA_PATTERNS.get(cmd_name)
        if pattern:
            if not re.match(pattern, part):
                return False, f"指令格式错误: {part}"
    
    # 执行扩展模块的后验证钩子
    for hook in get_hooks('validate_post'):
        result = hook['func'](cmd_str)
        if result is not None:
            return result
    
    return True, ""

def gen_tone(freq, sec):
    n = int(SAMPLE_RATE * sec)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        val = int(VOLUME * math.sin(2 * math.pi * freq * t))
        samples.append(max(-32768, min(32767, val)))
    return samples

def gen_silence(sec):
    return [0] * int(SAMPLE_RATE * sec)

def encode_symbol(val):
    return gen_tone(FREQ_SYM[val], SYM_DUR)

def encode_byte(byte):
    b1 = (byte >> 5) & 0x07
    b2 = (byte >> 2) & 0x07
    b3 = byte & 0x07
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
║                    音频管理通道协议 - 编码器 v1.3                           ║
╠════════════════════════════════════════════════════════════════════════════╣
║ 用法: python encoder.py "指令"                                            ║
║                                                                             ║
║ 示例:                                                                       ║
║   python encoder.py "PING"                                                 ║
║   python encoder.py "MOVE 100;TURN 90;STOP"                                ║
║   python encoder.py "SCREEN_COLOR 255 0 0;LED_ON"                          ║
║                                                                             ║
║ 指令列表:                                                                   ║
║   系统: NOP, STOP, STATUS, PING, REBOOT, SHUTDOWN, RESET                   ║
║         LOCK, UNLOCK, SLEEP, WAKE                                          ║
║   运动: MOVE 距离, TURN 角度(0-3600), SPEED 速度(0-255)                    ║
║         STOP_MOVE, HOME                                                    ║
║   外设: SCREEN_ON, SCREEN_OFF, SCREEN_COLOR R G B                          ║
║         LED_ON, LED_OFF, LED_COLOR R G B, CAMERA_ON, CAMERA_OFF            ║
║         VOLUME 音量, MUTE, UNMUTE                                          ║
║   媒体: PLAY, PAUSE, RESUME, STOP, NEXT, PREV, REPEAT 模式, SHUFFLE 开关   ║
║                                                                             ║
║ 输出文件: cmd.wav                                                           ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    ok, err = validate_command(cmd)
    if not ok:
        print(f"[ERROR] {err}")
        sys.exit(1)
    
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