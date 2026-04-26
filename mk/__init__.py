# mk/__init__.py
"""
光圈科技音频协议 - 模块自动加载器

支持钩子:
- encode_pre / encode_post: 编码前后处理
- decode_pre / decode_post: 解码前后处理
- validate_pre / validate_post: 指令验证前后处理
"""

import os
import importlib.util
from collections import defaultdict

_HOOKS = defaultdict(list)
_MODULES = []
_LOADED = False

# 支持的钩子类型
HOOK_TYPES = [
    'encode_pre', 'encode_post',
    'decode_pre', 'decode_post',
    'validate_pre', 'validate_post'
]

def _load_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Cannot load module {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_modules(mk_dir=None):
    global _LOADED
    if _LOADED:
        return
    
    if mk_dir is None:
        possible_paths = [
            os.path.join(os.getcwd(), 'mk'),
            os.path.join(os.path.dirname(__file__), '..', 'mk'),
            os.path.join(os.path.dirname(__file__)),
        ]
        for path in possible_paths:
            if os.path.exists(path) and os.path.isdir(path):
                mk_dir = path
                break
    
    if not mk_dir or not os.path.exists(mk_dir):
        _LOADED = True
        return
    
    for filename in sorted(os.listdir(mk_dir)):
        if filename.startswith('module_') and filename.endswith('.py'):
            module_path = os.path.join(mk_dir, filename)
            module_name = f"mk_{filename[:-3]}"
            try:
                module = _load_module_from_path(module_name, module_path)
                if hasattr(module, 'register'):
                    info = module.register()
                    _MODULES.append(info)
                    for hook in info.get('hooks', []):
                        if hook in HOOK_TYPES:
                            hook_func = getattr(module, f'hook_{hook}', None)
                            if hook_func:
                                _HOOKS[hook].append(hook_func)
                    print(f"[MODULE] 已加载: {info.get('name')} v{info.get('version')}")
                else:
                    print(f"[MODULE] 警告: {filename} 缺少 register()")
            except Exception as e:
                print(f"[MODULE] 错误: {filename} - {e}")
    
    _LOADED = True

def ensure_loaded():
    if not _LOADED:
        load_modules()

def get_hooks(hook_name):
    ensure_loaded()
    return _HOOKS.get(hook_name, [])

def get_modules():
    ensure_loaded()
    return _MODULES.copy()

def clear_modules():
    global _HOOKS, _MODULES, _LOADED
    _HOOKS = defaultdict(list)
    _MODULES = []
    _LOADED = False