# 最小替代版：原本的 _common.py 沒有上傳，這裡只補 run_demo.py 需要的兩個名稱。
import importlib.util, os
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "反向抽鬼牌vC7_0922v6.py")
def load_engine(path=None, module_name="engine"):
    path = path or DEFAULT
    spec = importlib.util.spec_from_file_location(module_name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m, os.path.basename(path)
