import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json
from typing import Any, Tuple, Union

# ---------------- 类型图标 ----------------
EMOJI = {
    dict: "📂", list: "📋", str: "📝",
    int: "🔢", float: "🔢", bool: "✔",
    type(None): "⬜"
}

# ---------------- 工具函数 ----------------
def _type_name(py_obj: Any) -> str:
    """返回给用户看的类型名字"""
    return {dict: "对象", list: "列表", str: "字符串",
            int: "整数", float: "小数", bool: "布尔", type(None): "空值"}.get(type(py_obj), "未知")

# ===================== 主程序 =====================
class JsonTreeEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSON 树形编辑器")
        self.geometry("800x500")
        self.file_path: str | None = None
        #  允许根为 list / str / int …
        self.data: Any = {}

        # ---------------- 工具栏 ----------------
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=5, pady=5)
        for txt, cmd in [("新建", self.add_key), ("重命名", self.rename_key),
                         ("删除", self.delete_key)]:
            ttk.Button(bar, text=txt, command=cmd).pack(side=tk.LEFT, padx=2)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        for txt, cmd in [("打开", self.load_file), ("保存", self.save_file),
                         ("另存为", self.save_as_file)]:
            ttk.Button(bar, text=txt, command=cmd).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="新建空白", command=self.new_blank).pack(side=tk.LEFT, padx=2)

        # ---------------- 左右 Paned ----------------
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(paned)
        paned.add(self.tree)
        right = ttk.Frame(paned)
        paned.add(right)
        ttk.Label(right, text="当前值（可直接编辑）：").pack(anchor=tk.W, padx=5, pady=2)
        self.value_text = tk.Text(right, width=40, height=12)
        self.value_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Button(right, text="应用修改", command=self.apply_value).pack(anchor=tk.E, padx=5, pady=2)

        # 右键菜单
        self.menu = tk.Menu(self, tearoff=0)
        for lbl, cmd in [("新建", self.add_key), ("重命名", self.rename_key),
                         ("删除", self.delete_key)]:
            self.menu.add_command(label=lbl, command=cmd)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.on_right_click)

        self._refresh_tree()

    # ---------------- 路径解析 ----------------
    def _parse_path(self, iid: str) -> Tuple[Union[dict, list], Union[str, int]]:
        """
        把 tree.iid 解析成 (parent_container, key_or_index)
        根节点 $root 特殊处理
        """
        if iid == "$root":
            return self.data, None  # type: ignore
        parts = [p for p in iid.split("/") if p]
        node: Any = self.data
        for p in parts[:-1]:
            if isinstance(node, dict):
                node = node[p]
            elif isinstance(node, list):
                idx = int(p[1:-1])
                node = node[idx]
            else:
                raise ValueError(f"非法路径: {iid}")
        last = parts[-1]
        if isinstance(node, dict):
            return node, last
        elif isinstance(node, list):
            return node, int(last[1:-1])
        else:
            raise ValueError(f"非法路径: {iid}")

    # ---------------- 树刷新 ----------------
    def _build_tree(self, parent="", path="/", obj=None):
        obj = self.data if obj is None else obj
        if parent == "" and isinstance(obj, dict):
            # 虚拟根
            self.tree.insert("", tk.END, iid="$root", text="📂 $ROOT", open=True)
            parent, path = "$root", "/"
        if isinstance(obj, dict):
            for k, v in obj.items():
                cur = f"{path}{k}"
                #self.tree.insert(parent, tk.END, iid=cur,
                #                text=f"{EMOJI.get(type(v), '?')} {k}", open=True)
                icon = EMOJI.get(type(v), '?')
                if isinstance(v, bool):
                    icon = "✅" if v else "❌"
                self.tree.insert(parent, tk.END, iid=cur,
                 text=f"{icon} {k}", open=True)
                if isinstance(v, (dict, list)):
                    self._build_tree(cur, cur + "/", v)
        elif isinstance(obj, list):
            for idx, v in enumerate(obj):
                cur = f"{path}[{idx}]"
                self.tree.insert(parent, tk.END, iid=cur,
                 text=f"{EMOJI.get(type(v), '?')} [{idx}]", open=True)
                if isinstance(v, (dict, list)):
                    self._build_tree(cur, cur + "/", v)

    def _refresh_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._build_tree()

    # ---------------- 事件 ----------------
    def on_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            container, key_or_idx = self._parse_path(iid)
            if key_or_idx is None:  # $root 本身
                value = container
            else:
                value = container[key_or_idx]
        except Exception as e:
            messagebox.showwarning("路径失效", f"{e}\n即将自动刷新树")
            self._refresh_tree()
            return
        self.value_text.delete(1.0, tk.END)
        self.value_text.insert(tk.END, json.dumps(value, ensure_ascii=False, indent=2))

    def on_right_click(self, evt):
        item = self.tree.identify_row(evt.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(evt.x_root, evt.y_root)

    # ---------------- 新建向导 ----------------
    def add_key(self):
        sel = self.tree.selection()
        if not sel:
            target_node, target_path = self.data, "/"
        else:
            container, key_or_idx = self._parse_path(sel[0])
            if key_or_idx is None:  # 选中 $root
                target_node, target_path = container, "/"
            else:
                value = container[key_or_idx]
                if not isinstance(value, (dict, list)):
                    messagebox.showwarning("提示", "只能给「对象」或「列表」添加子项")
                    return
                target_node, target_path = value, sel[0] + "/"

        # 弹窗选类型
        typ = self._ask_new_type()
        if not typ:
            return

        # 根据不同类型收集数据
        if isinstance(target_node, dict):
            name = simpledialog.askstring("新建", "请输入键名：")
            if not name or name in target_node:
                messagebox.showerror("错误", "键名为空或已存在")
                return
            target_node[name] = self._default_value_by_type(typ)
        elif isinstance(target_node, list):
            target_node.append(self._default_value_by_type(typ))
        self._refresh_tree()

    # ---------------- 弹窗：选择新建类型 ----------------
    def _ask_new_type(self) -> str | None:
        top = tk.Toplevel(self)
        top.title("选择新建类型")
        top.grab_set()
        top.resizable(False, False)
        tk.Label(top, text="请选择要新建的类型：").pack(pady=6)
        v = tk.StringVar(value="dict")
        for t, txt in [("dict", "对象"), ("list", "列表"),
                       ("str", "字符串"), ("num", "数字"),
                       ("bool", "布尔"), ("null", "空值")]:
            tk.Radiobutton(top, text=txt, variable=v, value=t).pack(anchor=tk.W, padx=20)
        tk.Frame(top).pack(pady=4)
        ok = tk.Button(top, text="确定", command=top.destroy)
        ok.pack(pady=6)
        ok.focus()
        self.wait_window(top)
        return v.get() or None

    def _default_value_by_type(self, typ: str) -> Any:
        return {"dict": {}, "list": [], "str": "", "num": 0,
                "bool": False, "null": None}[typ]

    # ---------------- 重命名 ----------------
    def rename_key(self):
        sel = self.tree.selection()
        if not sel:
            return
        container, key_or_idx = self._parse_path(sel[0])
        if key_or_idx is None:
            messagebox.showwarning("提示", "不能重命名根节点")
            return
        if not isinstance(container, dict):
            messagebox.showwarning("提示", "仅对象下的键可重命名")
            return
        old = key_or_idx
        new = simpledialog.askstring("重命名", "新名称：", initialvalue=old)
        if not new or new == old:
            return
        if new in container:
            messagebox.showerror("错误", "名称已存在")
            return
        container[new] = container.pop(old)
        self._refresh_tree()

    # ---------------- 删除 ----------------
    def delete_key(self):
        sel = self.tree.selection()
        if not sel:
            return
        container, key_or_idx = self._parse_path(sel[0])
        if key_or_idx is None:
            messagebox.showwarning("提示", "不能删除根节点")
            return
        key_repr = key_or_idx if isinstance(container, dict) else f"[{key_or_idx}]"
        if not messagebox.askyesno("确认", f"删除键 {key_repr}？"):
            return
        del container[key_or_idx]
        self._refresh_tree()

    # ---------------- 应用右侧编辑 ----------------
    def apply_value(self):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            new_val = json.loads(self.value_text.get(1.0, tk.END))
        except Exception as e:
            messagebox.showerror("非法 JSON", f"解析失败：{e}")
            return
        container, key_or_idx = self._parse_path(sel[0])
        if key_or_idx is None:  # 改的是 $root
            if not isinstance(new_val, dict):
                messagebox.showerror("错误", "根节点必须是对象")
                return
            self.data.clear()
            self.data.update(new_val)
        else:
            container[key_or_idx] = new_val
        self._refresh_tree()

    # ---------------- 文件 IO ----------------
    def load_file(self):
        file = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not file:
            return
        try:
            with open(file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("JSON 根必须是对象")
            self.data = loaded
            if not isinstance(self.data, dict):
                self.data = {"$root": self.data}      # 内存包一层，磁盘保持原样
            self.file_path = file
            self._refresh_tree()
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def save_file(self):
        self.file_path and self._do_save(self.file_path) or self.save_as_file()

    def save_as_file(self):
        file = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if file:
            self._do_save(file)
            self.file_path = file

    def _do_save(self, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                to_save = self.data.get("$root") if isinstance(self.data, dict) and "$root" in self.data else self.data
                json.dump(to_save, f, ensure_ascii=False, indent=2)
                #json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("提示", "已保存")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
    def new_blank(self):
        self.data = {}
        self.file_path = None
        self._refresh_tree()

# ---------------- main ----------------
if __name__ == "__main__":
    JsonTreeEditor().mainloop()