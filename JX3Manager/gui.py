import customtkinter as ctk

from PIL import Image, ImageTk

from tkinter import ttk

import os, sys, csv, re, threading, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import JX3Manager

from readers.dungeon_cd import DUNGEON_NAMES

from readers.plugin_settings import enable_all_stats

from logger import get_logger



logger = get_logger(__name__)



ctk.set_appearance_mode("dark")

ctk.set_default_color_theme("blue")



# Style ttk widgets to match dark theme

style = ttk.Style()

style.theme_use("clam")

style.configure("Treeview", background="#1a1a2e", foreground="#c9d1d9",

                fieldbackground="#1a1a2e", font=("Microsoft YaHei UI", 10),

                rowheight=28)

style.configure("Treeview.Heading", background="#15152a", foreground="#8b949e",

                font=("Microsoft YaHei UI", 9, "bold"))

style.map("Treeview", background=[("selected", "#1f3a5f")],

          foreground=[("selected", "#fff")])

style.layout("Vertical.TScrollbar", [])



FONT = ctk.CTkFont(family="Microsoft YaHei UI", size=13)

FONT_SM = ctk.CTkFont(family="Microsoft YaHei UI", size=12)

FONT_XS = ctk.CTkFont(family="Microsoft YaHei UI", size=11)

FONT_MONO = ctk.CTkFont(family="Consolas", size=12)

FONT_H = ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold")

FONT_H2 = ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")



class App:

    def __init__(self):

        self.mgr = JX3Manager()

        self.root = ctk.CTk()

        self.root.title("剑网3 多角色管理器")

        self.root.geometry("1320x820")

        self._sort_state = {}

        self._all_chars = []

        self._filter_text = ""

        self._ui()

        self.root.after(200, self._check_config_and_start)

    def _check_config_and_start(self):
        from config_loader import get_cached_config, validate_config
        config = get_cached_config()
        errors = validate_config(config)
        if errors:
            self._show_config_dialog(config)
        else:
            self.refresh()
            
    def _show_config_dialog(self, config):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("初次运行 / 配置缺失")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="请设置以下必填信息：", font=FONT_H2).pack(pady=10)
        
        path_var = ctk.StringVar(value=config.get("game_path", ""))
        ctk.CTkLabel(dialog, text="游戏路径 (例如 D:\\JX3_Classic):").pack(anchor="w", padx=20)
        ctk.CTkEntry(dialog, textvariable=path_var, width=460).pack(padx=20, pady=5)
        
        token_var = ctk.StringVar(value=config.get("api_key", ""))
        ctk.CTkLabel(dialog, text="JX3API Token:").pack(anchor="w", padx=20)
        ctk.CTkEntry(dialog, textvariable=token_var, width=460).pack(padx=20, pady=5)
        
        def save():
            config["game_path"] = path_var.get().strip()
            config["api_key"] = token_var.get().strip()
            from config_loader import save_config, validate_config
            if validate_config(config):
                pass
            save_config(config)
            self.mgr = JX3Manager() # reload manager with new path
            dialog.destroy()
            self.refresh()
            
        ctk.CTkButton(dialog, text="保存并启动", command=save).pack(pady=20)



    def _ui(self):

        # Header

        h = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")

        h.pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(h, text="剑网3 多角色管理器", font=FONT_H,

                      text_color="#3b8ed0").pack(side="left")

        self.st = ctk.CTkLabel(h, text="就绪", font=FONT_XS,

                                text_color="#888")

        self.st.pack(side="right")



        # Toolbar

        tb = ctk.CTkFrame(self.root, corner_radius=8, fg_color="#1a1a2e")

        tb.pack(fill="x", padx=24, pady=(4, 8))



        g1 = ctk.CTkFrame(tb, fg_color="transparent")

        g1.pack(side="left", padx=4)

        ctk.CTkButton(g1, text="⟳  刷新", command=self.refresh,

                       font=FONT_SM, width=90, height=30).pack(side="left", padx=3)

        ctk.CTkButton(g1, text="◎  百战查询", command=self.fetch_bz,

                       font=FONT_SM, width=100, height=30).pack(side="left", padx=3)



        ctk.CTkLabel(tb, text="|", text_color="#444").pack(side="left", padx=6)



        g2 = ctk.CTkFrame(tb, fg_color="transparent")

        g2.pack(side="left", padx=4)

        ctk.CTkButton(g2, text="◉  开启统计", command=self.enable_stats,

                       font=FONT_SM, width=100, height=30, fg_color="#2d4a2d",

                       hover_color="#3a6a3a").pack(side="left", padx=3)



        ctk.CTkLabel(tb, text="|", text_color="#444").pack(side="left", padx=6)



        g3 = ctk.CTkFrame(tb, fg_color="transparent")

        g3.pack(side="left", padx=4)

        ctk.CTkButton(g3, text="⬇  JSON", command=self.export_json,

                       font=FONT_SM, width=80, height=30, fg_color="#2d3a4d",

                       hover_color="#3a5a6a").pack(side="left", padx=3)

        ctk.CTkButton(g3, text="⬇  CSV", command=self.export_csv,

                       font=FONT_SM, width=80, height=30, fg_color="#2d3a4d",

                       hover_color="#3a5a6a").pack(side="left", padx=3)



        ctk.CTkLabel(tb, text="|", text_color="#444").pack(side="left", padx=6)



        # Combat Log Config button group

        g4 = ctk.CTkFrame(tb, fg_color="transparent")

        g4.pack(side="left", padx=4)

        ctk.CTkButton(g4, text="⚙  战斗日志配置", command=self.configure_combat_logs,

                       font=FONT_SM, width=120, height=30, fg_color="#4a2d5a",

                       hover_color="#6a3a7a").pack(side="left", padx=3)



        ctk.CTkLabel(tb, text="|", text_color="#444").pack(side="left", padx=6)



        ctk.CTkLabel(tb, text="服务器:", font=FONT_XS).pack(side="left", padx=(4, 2))

        self.svf = ctk.CTkComboBox(tb, values=["所有服务器"], width=160,

                                    font=FONT_SM, state="readonly",

                                    command=lambda _: self._apply_filters())

        self.svf.pack(side="left", padx=2)



        # Search

        sr = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")

        sr.pack(fill="x", padx=24, pady=(0, 10))



        sbox = ctk.CTkFrame(sr, corner_radius=8, fg_color="#1a1a2e",

                             border_width=1, border_color="#2a2a4e")

        sbox.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(sbox, text="🔍", font=FONT, text_color="#666"

                     ).pack(side="left", padx=(10, 4))

        self.search_entry = ctk.CTkEntry(sbox, placeholder_text="输入角色名快速过滤",

                                           font=FONT, fg_color="transparent",

                                           border_width=0)

        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10),

                               pady=8)

        self.search_entry.bind("<KeyRelease>", lambda _: self._apply_filters())



        # Main area

        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")

        main.pack(fill="both", expand=True, padx=24, pady=(0, 16))



        # Left: Character list

        left = ctk.CTkFrame(main, corner_radius=8, fg_color="#1a1a2e", width=380)

        left.pack(side="left", fill="y", padx=(0, 12))

        left.pack_propagate(False)



        self.tree = ttk.Treeview(left, columns=("name", "server", "school", "level", "equip", "gold"),

                                  show="headings", selectmode="browse")

        for col, w, anchor in [

            ("name", 100, "w"), ("server", 100, "w"),

            ("school", 70, "center"), ("level", 50, "center"),

            ("equip", 70, "center"), ("gold", 70, "center"),

        ]:

            self.tree.heading(col, text=col.capitalize(),

                               command=lambda c=col: self._sort(c))

            self.tree.column(col, width=w, anchor=anchor, stretch=False)

        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.tree.bind("<<TreeviewSelect>>", lambda _: self._detail())



        # Right: Detail tabs

        right = ctk.CTkFrame(main, corner_radius=0, fg_color="transparent")

        right.pack(side="left", fill="both", expand=True)



        self.nb = ttk.Notebook(right)

        self.nb.pack(fill="both", expand=True)



        # Tab 1: Overview

        self.tab_overview = ctk.CTkFrame(self.nb, corner_radius=0, fg_color="transparent")

        self.nb.add(self.tab_overview, text=" 总览 ")



        # Tab 2: 百战

        self.tab_bz = ctk.CTkFrame(self.nb, corner_radius=0, fg_color="transparent")

        self.nb.add(self.tab_bz, text=" 百战 ")

        self.bz_tree = ttk.Treeview(self.tab_bz,

                                     columns=("name", "server", "killed", "total", "xiuluo"),

                                     show="headings", selectmode="browse")

        for col, w, anchor in [

            ("name", 100, "w"), ("server", 120, "w"),

            ("killed", 60, "center"), ("total", 60, "center"),

            ("xiuluo", 60, "center"),

        ]:

            self.bz_tree.heading(col, text=col.capitalize())

            self.bz_tree.column(col, width=w, anchor=anchor, stretch=False)

        self.bz_tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.bz_tree.tag_configure("done", background="#1a3a2a")



        # Tab 3: 副本CD

        self.tab_cd = ctk.CTkFrame(self.nb, corner_radius=0, fg_color="transparent")

        self.nb.add(self.tab_cd, text=" 副本CD ")

        self.cd_tree = ttk.Treeview(self.tab_cd,

                                     columns=("name", "server", "dungeon", "progress", "count"),

                                     show="headings", selectmode="browse")

        for col, w, anchor in [

            ("name", 100, "w"), ("server", 120, "w"),

            ("dungeon", 140, "w"), ("progress", 200, "w"),

            ("count", 80, "center"),

        ]:

            self.cd_tree.heading(col, text=col.capitalize())

            self.cd_tree.column(col, width=w, anchor=anchor, stretch=False)

        self.cd_tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.cd_tree.tag_configure("done", background="#1a3a2a")



        # Tab 4: 百战技能 (Web-style card layout)

        self.tab_bz_skill = ctk.CTkFrame(self.nb, corner_radius=0, fg_color="transparent")

        self.nb.add(self.tab_bz_skill, text=" 百战技能 ")

        

        # Filter bar

        self.bz_filter_frame = ctk.CTkFrame(self.tab_bz_skill, fg_color="transparent")

        self.bz_filter_frame.pack(fill="x", padx=8, pady=(8, 4))

        

        # Search

        self.bz_search = ctk.CTkEntry(self.bz_filter_frame, placeholder_text="搜索技能...", width=200)

        self.bz_search.pack(side="left", padx=4)

        self.bz_search.bind("<KeyRelease>", lambda e: self._update_bz_skill_tab())

        

        # Color filter label

        ctk.CTkLabel(self.bz_filter_frame, text="破绽:", font=FONT_XS).pack(side="left", padx=(8, 2))

        

        # Color filter buttons

        self.bz_color_filters = {}

        BZ_COLORS = {2: '#ffcc00', 3: '#4488ff', 4: '#44cc44', 5: '#ff4444', 6: '#bb44ff', 7: '#333333', 0: '#aaaaaa'}

        COLOR_NAMES = {2: '黄', 3: '蓝', 4: '绿', 5: '红', 6: '紫', 7: '黑', 0: '白'}

        # Pre-computed color variants for UI (since customtkinter does not support 8-digit hex)

        BZ_COLOR_LIGHT = {"#ffcc00": "#4d3300", "#4488ff": "#0d1b33", "#44cc44": "#0d330d", "#ff4444": "#4d0d0d", "#bb44ff": "#2d0d4d", "#333333": "#0a0a0a", "#aaaaaa": "#222222"}

        BZ_COLOR_MEDIUM = {"#ffcc00": "#996600", "#4488ff": "#1a3366", "#44cc44": "#1a661a", "#ff4444": "#991a1a", "#bb44ff": "#5a1a99", "#333333": "#151515", "#aaaaaa": "#444444"}

        BZ_COLOR_ACTIVE = {"#ffcc00": "#cc9900", "#4488ff": "#264d99", "#44cc44": "#269926", "#ff4444": "#cc2626", "#bb44ff": "#8c26cc", "#333333": "#1f1f1f", "#aaaaaa": "#666666"}

        self.bz_active_color = None

        for color_id, color_hex in BZ_COLORS.items():

            name = COLOR_NAMES.get(color_id, str(color_id))

            btn = ctk.CTkButton(self.bz_filter_frame, text=name, width=36, height=22,

                               fg_color=BZ_COLOR_LIGHT[color_hex], text_color=color_hex,

                               hover_color=BZ_COLOR_MEDIUM[color_hex],

                               border_color=color_hex, border_width=1,

                               command=lambda cid=color_id: self._set_bz_color_filter(cid))

            btn.pack(side="left", padx=1)

            self.bz_color_filters[color_id] = btn

        

        # Type filter label

        ctk.CTkLabel(self.bz_filter_frame, text="  类型:", font=FONT_XS).pack(side="left", padx=(8, 2))

        

        # Type filter buttons

        self.bz_type_filters = {}

        TYPE_LABELS = {'攻击': '攻击', '控制': '控制', '位移': '位移', '治疗': '治疗', '特殊': '特殊'}

        self.bz_active_type = None

        for type_name in TYPE_LABELS:

            btn = ctk.CTkButton(self.bz_filter_frame, text=type_name, width=48, height=22,

                               fg_color="#2a2a4a", text_color="#888888",

                               hover_color="#3a3a5a", border_color="#444444", border_width=1,

                               command=lambda t=type_name: self._set_bz_type_filter(t))

            btn.pack(side="left", padx=1)

            self.bz_type_filters[type_name] = btn

        

        # Clear filters button

        ctk.CTkButton(self.bz_filter_frame, text="清除", width=40, height=22,

                     command=self._clear_bz_filters).pack(side="left", padx=4)

        

        # Skill cards container (scrollable)

        self.bz_skill_container = ctk.CTkScrollableFrame(self.tab_bz_skill, fg_color="transparent")

        self.bz_skill_container.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        

        # No skills placeholder

        self.bz_empty_label = ctk.CTkLabel(self.bz_skill_container, text='请先选择角色并点击"百战查询"获取数据', 

                                           font=FONT, text_color="#888888")

        self.bz_empty_label.pack(pady=40)



    def _sort(self, col):

        reverse = self._sort_state.get(col, False)

        self._sort_state[col] = not reverse

        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        try:

            items.sort(key=lambda x: float(x[0]) if x[0].replace(".", "").isdigit() else x[0], reverse=reverse)

        except:

            items.sort(key=lambda x: x[0], reverse=reverse)

        for idx, (_, k) in enumerate(items):

            self.tree.move(k, "", idx)



    def _apply_filters(self):

        text = self.search_entry.get().lower().strip()

        self._filter_text = text

        server = self.svf.get()

        self._refresh_tree()



    def _refresh_tree(self):

        self.tree.delete(*self.tree.get_children())

        servers = set()

        for c in self._all_chars:

            name = c.get("name", "")

            if self._filter_text and self._filter_text not in name.lower():

                continue

            svr = f"{c.get('region', '')}/{c.get('server', '')}"

            server = self.svf.get()

            if server != "所有服务器" and server != svr:

                continue

            servers.add(svr)

            vals = (name, svr, c.get("force_name", ""),

                    c.get("level", ""), c.get("equip_score", 0),

                    c.get("gold", 0))

            self.tree.insert("", "end", values=vals)

        # Update server filter

        current = self.svf.get()

        vals = ["所有服务器"] + sorted(servers)

        self.svf.configure(values=vals)

        if current in vals:

            self.svf.set(current)

        else:

            self.svf.set("所有服务器")



    def refresh(self):

        self.st.configure(text="正在刷新...")

        self.root.update()

        def do():

            try:

                self.mgr.load_all()

                self._all_chars = sorted(

                    self.mgr.characters.values(),

                    key=lambda x: (x.get("region", ""), x.get("server", ""), x.get("name", ""))

                )

                self.root.after(0, self._on_refresh_done)

            except Exception as e:

                logger.exception("Refresh failed")

                self.root.after(0, lambda: self.st.configure(text=f"刷新失败: {e}"))

        threading.Thread(target=do, daemon=True).start()



    def _on_refresh_done(self):

        self._refresh_tree()

        self._detail()

        self._update_bz_tab()

        self._update_cd_tab()

        self.st.configure(text=f"就绪 ({len(self._all_chars)} 角色)")

        logger.info(f"GUI refreshed: {len(self._all_chars)} characters")



    def _detail(self):

        sel = self.tree.selection()

        if not sel:

            return

        name = self.tree.item(sel[0], "values")[0]

        c = next((x for x in self._all_chars if x.get("name") == name), None)

        if not c:

            return



        # Clear and rebuild

        for w in self.tab_overview.winfo_children():

            w.destroy()



        # Basic info card

        info_card = ctk.CTkFrame(self.tab_overview, corner_radius=8, fg_color="#1a1a2e")

        info_card.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(info_card, text=f"{name}", font=FONT_H2, text_color="#3b8ed0").pack(anchor="w", padx=16, pady=(12, 4))

        meta = f"{c.get('region', '')}/{c.get('server', '')}  |  {c.get('force_name', '')}  |  Lv.{c.get('level', '?')}"

        ctk.CTkLabel(info_card, text=meta, font=FONT, text_color="#888").pack(anchor="w", padx=16, pady=(0, 8))



        # Stats grid

        grid = ctk.CTkFrame(info_card, fg_color="transparent")

        grid.pack(fill="x", padx=16, pady=(0, 12))

        for i, (lbl, val, color) in enumerate([

            ("装备分", c.get('equip_score', 0), "#3b8ed0"),

            ("金币", f"{c.get('gold', 0):,}", "#d2991d"),

            ("贡献度", c.get('contribution', 0), "#58a6ff"),

            ("公正值", c.get('justice', 0), "#a371f7"),

            ("宠物分", c.get('pet_score', 0), "#d2753b"),

            ("成就", c.get('achievement_score', 0), "#3fb950"),

        ]):

            cell = ctk.CTkFrame(grid, corner_radius=6, fg_color="#0d1117", border_width=1, border_color="#30363d")

            cell.grid(row=0, column=i, padx=4, pady=4, sticky="ew")

            grid.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(cell, text=lbl, font=FONT_XS, text_color="#888").pack(pady=(8, 0))

            ctk.CTkLabel(cell, text=str(val), font=FONT_MONO, text_color=color).pack(pady=(0, 8))



        # 百战进度卡

        prog = c.get("baizhan_progress", {})

        if prog:

            bz_card = ctk.CTkFrame(self.tab_overview, corner_radius=8, fg_color="#1a1a2e")

            bz_card.pack(fill="x", padx=12, pady=8)

            ctk.CTkLabel(bz_card, text="百战异闻录 (0-100层)", font=FONT_H2, text_color="#a371f7").pack(anchor="w", padx=16, pady=(12, 8))

            

            row = ctk.CTkFrame(bz_card, fg_color="transparent")

            row.pack(fill="x", padx=16, pady=(0, 12))

            killed = prog.get('killed', 0)

            total = prog.get('total', 100)

            pct = killed / total * 100 if total else 0

            bar = ctk.CTkProgressBar(row, width=300, height=16, progress_color="#a371f7")

            bar.set(pct / 100)

            bar.pack(side="left", padx=6)

            ctk.CTkLabel(row, text=f"{killed}/{total} ({pct:.0f}%)", font=FONT_MONO).pack(side="left")

            ctk.CTkLabel(row, text={"是": "✓ 已击杀", "否": "✗ 未击杀"}["是" if prog.get('xiuluo') else "否"], font=FONT_SM, text_color="#3fb950" if prog.get('xiuluo') else "#f85149").pack(side="left", padx=6)

        # (removed duplicate killed/total display)

        else:

            ctk.CTkLabel(self.tab_overview, text="无百战进度数据", font=FONT_SM, text_color="#888").pack(anchor="w", padx=12)



        # 副本CD卡

        cd = c.get("dungeon_cd", {})

        if cd:

            cd_card = ctk.CTkFrame(self.tab_overview, corner_radius=8, fg_color="#1a1a2e")

            cd_card.pack(fill="x", padx=12, pady=8)

            ctk.CTkLabel(cd_card, text="副本 CD", font=FONT_H2, text_color="#58a6ff").pack(anchor="w", padx=16, pady=(12, 8))

            for did, info in sorted(cd.items()):

                dname = DUNGEON_NAMES.get(did, info.get("name", f"D{did}"))

                done = info["done"]

                total = info["total"]

                stl = "green" if done >= total else ("yellow" if done > 0 else "red")

                row = ctk.CTkFrame(cd_card, fg_color="transparent")

                row.pack(fill="x", padx=16, pady=4)

                ctk.CTkLabel(row, text=dname, font=FONT_SM, width=130, anchor="w").pack(side="left")

                bar = ctk.CTkProgressBar(row, width=200, height=12, progress_color={

                    "green": "#3fb950", "yellow": "#d2991d", "red": "#f85149"

                }[stl])

                bar.set(done / total if total else 0)

                bar.pack(side="left", padx=6)

                ctk.CTkLabel(row, text=f"{done}/{total}", font=FONT_MONO).pack(side="left")

        else:

            ctk.CTkLabel(self.tab_overview, text="无副本CD数据", font=FONT_SM, text_color="#888").pack(anchor="w", padx=12)



        ctk.CTkLabel(self.tab_overview, text="", height=20).pack()



    def _progress_text(self, done, total):

        if total == 0:

            return "-"

        pct = done / total * 100

        filled = int(pct / 100 * 20)

        bar = "█" * filled + "░" * (20 - filled)

        return f"{bar} {pct:.0f}%"



    def _update_bz_tab(self):

        self.bz_tree.delete(*self.bz_tree.get_children())

        for c in self._all_chars:

            p = c.get("baizhan_progress", {})

            if not p:

                continue

            xiuluo = "✓" if p.get("xiuluo") else "✗"

            vals = (c.get("name", ""),

                    f"{c.get('region', '')}/{c.get('server', '')}",

                    str(p.get("killed", 0)),

                    str(p.get("total", 0)), xiuluo)

            self.bz_tree.insert("", "end", values=vals,

                                 tags=("done",) if p.get("xiuluo") else ())



    def _update_cd_tab(self):

        self.cd_tree.delete(*self.cd_tree.get_children())

        for c in self._all_chars:

            cd = c.get("dungeon_cd", {})

            if not cd:

                continue

            for did, info in sorted(cd.items()):

                dname = DUNGEON_NAMES.get(did, info.get("name", f"D{did}"))

                done = info["done"]

                total = info["total"]

                bar = self._progress_text(done, total)

                vals = (c.get("name", ""),

                        f"{c.get('region', '')}/{c.get('server', '')}",

                        dname, bar, f"{done}/{total}")

                self.cd_tree.insert("", "end", values=vals,

                                     tags=("done",) if done >= total else ())



    def _update_bz_skill_tab(self, name=None):
        """Canvas高性能渲染百战技能，悬停显示详情"""
        for attr in ("_bz_canvas", "_bz_content_frame", "_bz_tooltip"):
            if hasattr(self, attr) and getattr(self, attr):
                try: getattr(self, attr).destroy()
                except: pass
                setattr(self, attr, None)
        self._bz_icon_refs = []
        if not name:
            sel = self.tree.selection()
            if sel:
                vals = self.tree.item(sel[0], "values")
                name = vals[0] if vals else None
        if not name:
            self.bz_empty_label.pack(pady=40); return

        c = next((x for x in self._all_chars if x.get("name") == name), None)
        if not c: self.bz_empty_label.pack(pady=40); return

        baizhan_api = c.get("baizhan_api", {})
        skill_list = baizhan_api.get("skillList", [])
        if not skill_list:
            self.bz_empty_label.configure(text=f"{name} 暂无百战技能数据")
            self.bz_empty_label.pack(pady=40); return

        self.bz_empty_label.pack_forget()
        skill_descs_map = self._load_skill_descriptions()

        CH = {2:"#ffcc00",3:"#4488ff",4:"#44cc44",5:"#ff4444",6:"#bb44ff",7:"#333333",0:"#aaaaaa"}
        CN = {2:"黄",3:"蓝",4:"绿",5:"红",6:"紫",7:"黑",0:"白"}
        TM = {"1":"攻击","2":"攻击","3":"攻击","4":"攻击","5":"攻击",
              "6":"控制","7":"控制","8":"控制","9":"控制",
              "10":"位移","11":"治疗","12":"特殊","13":"位移","14":"位移"}

        st = self.bz_search.get().lower().strip() if hasattr(self,"bz_search") else ""
        ac = getattr(self, "bz_active_color", None)
        atp = getattr(self, "bz_active_type", None)

        from collections import OrderedDict
        bg = OrderedDict(); cc = {}

        for sk in skill_list:
            boss = sk.get("szBossName",""); sn = sk.get("szSkillName","")
            lv = sk.get("nLevel",0); col = sk.get("nColor",0)
            zt = sk.get("szType",""); iid = sk.get("dwInSkillID",0)
            cn = CN.get(col,str(col)); ch = CH.get(col,"#aaaaaa")
            ts = set()
            if zt:
                for t in zt.split(";"): ts.add(TM.get(t,t))
            tstr = ",".join(sorted(ts)) if ts else "-"
            if st and st not in sn.lower() and st not in boss.lower(): continue
            if ac is not None and col != ac: continue
            if atp is not None and atp not in tstr: continue
            cc[cn] = cc.get(cn,0)+1
            if boss not in bg: bg[boss] = []
            bg[boss].append({
                "boss":boss,"sn":sn,"lv":lv,
                "cn":cn,"ch":ch,"tstr":tstr,"iid":iid,
                "desc":skill_descs_map.get(sn,"")})

        if not bg:
            self.bz_empty_label.configure(text="没有匹配的技能")
            self.bz_empty_label.pack(pady=40); return

        # Synchronous icon download (avoid race conditions)
        import requests
        cd = os.path.join(os.path.dirname(__file__),"data","bz_cache","icons")
        os.makedirs(cd, exist_ok=True)
        ld = os.path.join(os.path.dirname(__file__),"web","icons")
        for sk_ in skill_list:
            iid = sk_.get("dwInSkillID",0)
            if iid:
                fp = os.path.join(cd, f"{iid}.png")
                if not os.path.exists(fp):
                    try:
                        r = requests.get(f"https://icon.jx3box.com/icon/{iid}.png", timeout=5)
                        if r.status_code == 200:
                            with open(fp,"wb") as f: f.write(r.content)
                    except:
                        pass

        import tkinter as tk
        from PIL import Image

        # Replace scrollable frame with canvas (better performance)
        self.bz_skill_container.pack_forget()
        cf = ctk.CTkFrame(self.tab_bz_skill, fg_color="transparent")
        cf.pack(fill="both", expand=True)
        self._bz_content_frame = cf

        tf = ctk.CTkFrame(cf, fg_color="transparent")
        tf.pack(fill="x", padx=10, pady=(5,2))
        ts = sum(len(v) for v in bg.values())
        ctk.CTkLabel(tf, text=f"{name} 的百战技能",
            font=("Microsoft YaHei UI",16,"bold"),text_color="#e0e0e0").pack(anchor="w")
        it = f"共{ts}技能|{len(bg)}首领"
        if st: it += f" | 搜索:{st}"
        ctk.CTkLabel(tf, text=it, font=FONT_XS,text_color="#888").pack(anchor="w")

        if cc and not st and ac is None:
            sf = ctk.CTkFrame(cf,fg_color="transparent")
            sf.pack(fill="x",padx=10,pady=(2,6))
            dsp = {"黄":"#ffcc00","蓝":"#4488ff","绿":"#44cc44",
                   "红":"#ff4444","紫":"#bb44ff","黑":"#333333","白":"#aaaaaa"}
            for cn in ("黄","蓝","绿","红","紫","黑","白"):
                cnt = cc.get(cn,0)
                if cnt>0:
                    b = ctk.CTkFrame(sf,fg_color=dsp[cn],corner_radius=4)
                    b.pack(side="left",padx=(0,4))
                    tc = "#fff" if cn in ("黑","蓝","红","紫") else "#222"
                    ctk.CTkLabel(b,text=f" {cn}{cnt} ",font=FONT_XS,text_color=tc).pack(padx=4,pady=1)

        cvf = ctk.CTkFrame(cf,fg_color="transparent")
        cvf.pack(fill="both",expand=True,padx=10,pady=(0,8))
        self._bz_canvas = tk.Canvas(cvf,bg="#15152a",highlightthickness=0)
        sb = ctk.CTkScrollbar(cvf,orientation="vertical",command=self._bz_canvas.yview)
        self._bz_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right",fill="y")
        self._bz_canvas.pack(side="left",fill="both",expand=True)
        self._bz_canvas.bind("<MouseWheel>",
            lambda e: self._bz_canvas.yview_scroll(int(-1*(e.delta/120)),"units"))

        IS=48
        CW,CH=200,84; GP=10; BH=34
        y = 8
        g_idx = 0  # Global unique icon index

        for bname, skills in bg.items():
            self._bz_canvas.create_rectangle(4,y-2,800,y+BH-2,fill="#1e1e3a",outline="")
            self._bz_canvas.create_text(12,y,anchor="nw",text=f"  {bname}",
                font=("Microsoft YaHei UI",13,"bold"),fill="#c0c0e0")
            y += BH

            for i,sk in enumerate(skills):
                col = i%4; row = i//4
                cx = 6 + col*(CW+GP); cy = y + row*(CH+GP)
                rect = self._bz_canvas.create_rectangle(cx,cy,cx+CW,cy+CH,
                    fill="#252540",outline=sk["ch"],width=2)

                fp = os.path.join(cd,f"{sk['iid']}.png") if sk["iid"] else ""
                if not os.path.exists(fp):
                    fp = os.path.join(ld,f"{sk['sn']}.png")

                img_ref = None
                if os.path.exists(fp):
                    try:
                        img = Image.open(fp).resize((IS,IS),Image.Resampling.LANCZOS)
                        tki = ImageTk.PhotoImage(img)
                        self._bz_icon_refs.append(tki)
                        img_ref = tki
                    except Exception as e:
                        logger.error(f"Failed to load image {fp}: {e}")

                ix = cx + 8
                iy = cy + (CH-IS)//2
                if img_ref is not None:
                    # Color border around icon (破绽 type)
                    self._bz_canvas.create_rectangle(ix-2,iy-2,ix+IS+2,iy+IS+2,
                        fill="",outline=sk["ch"],width=2)
                    self._bz_canvas.create_image(ix,iy,anchor="nw",image=img_ref)
                else:
                    self._bz_canvas.create_rectangle(ix,iy,ix+IS,iy+IS,
                        fill=sk["ch"],outline="")
                    self._bz_canvas.create_text(ix+IS//2,iy+IS//2,
                        text=sk["sn"][0] if sk["sn"] else "?",
                        font=("Microsoft YaHei UI",20,"bold"),fill="#fff")

                tx = ix + IS + 10
                self._bz_canvas.create_text(tx,cy+14,anchor="nw",text=sk["sn"],
                    font=("Microsoft YaHei UI",12,"bold"),fill="#fff")
                self._bz_canvas.create_text(tx,cy+42,anchor="nw",
                    text=f"Lv.{sk['lv']}  {sk['cn']}",
                    font=("Microsoft YaHei UI",11),fill=sk["ch"])
                self._bz_canvas.create_text(cx+CW-4,cy+CH-4,anchor="se",
                    text=sk["boss"],font=("Microsoft YaHei UI",8),fill="#555")

                tag = f"cd{g_idx}"
                self._bz_canvas.addtag_withtag(tag,rect)
                self._bz_canvas.tag_bind(tag,"<Enter>",
                    lambda e,d=sk: self._show_bz_tooltip(e,d))
                self._bz_canvas.tag_bind(tag,"<Leave>",
                    lambda e: self._hide_bz_tooltip())

            y += ((len(skills)-1)//4+1)*(CH+GP)+6
        self._bz_canvas.configure(scrollregion=(0,0,800,y+10))

    def _show_bz_tooltip(self, event, skill_data):
        self._hide_bz_tooltip()
        import tkinter as tk
        tp = tk.Toplevel(self.root)
        tp.wm_overrideredirect(True)
        tp.wm_geometry(f"+{event.x_root+15}+{event.y_root+10}")
        tp.configure(bg="#333355")
        sd = skill_data
        lines = [
            f"【{sd[chr(115)+chr(110)]}】Lv.{sd[chr(108)+chr(118)]}",
            f"首领: {sd["boss"]}",
            f"破绽: {sd["cn"]} | 类型: {sd["tstr"]}",
        ]
        if sd.get("desc"): lines.append(""); lines.append(sd["desc"])
        for j, txt in enumerate(lines):
            fg = "#ffcc00" if j==0 else ("#aaa" if j==2 else "#ccc")
            lbl = tk.Label(tp, text=txt, bg="#333355", fg=fg,
                font=("Microsoft YaHei UI",10 if j==0 else 9),
                anchor="w", justify="left", wraplength=250)
            lbl.pack(fill="x", padx=10, pady=(2,0))
        self._bz_tooltip = tp

    def _hide_bz_tooltip(self):
        if hasattr(self,"_bz_tooltip") and self._bz_tooltip:
            try: self._bz_tooltip.destroy()
            except: pass
            self._bz_tooltip = None

    def _set_bz_color_filter(self, color_id):

        """Toggle color filter"""

        if getattr(self, "bz_active_color", None) == color_id:

            self.bz_active_color = None

        else:

            self.bz_active_color = color_id



        # Update button styles

        BZ_COLORS = {2: "#ffcc00", 3: "#4488ff", 4: "#44cc44", 5: "#ff4444", 6: "#bb44ff", 7: "#333333", 0: "#aaaaaa"}

        BZ_COLOR_LIGHT = {"#ffcc00": "#4d3300", "#4488ff": "#0d1b33", "#44cc44": "#0d330d", "#ff4444": "#4d0d0d", "#bb44ff": "#2d0d4d", "#333333": "#0a0a0a", "#aaaaaa": "#222222"}

        BZ_COLOR_ACTIVE = {"#ffcc00": "#cc9900", "#4488ff": "#264d99", "#44cc44": "#269926", "#ff4444": "#cc2626", "#bb44ff": "#8c26cc", "#333333": "#1f1f1f", "#aaaaaa": "#666666"}

        for cid, btn in getattr(self, "bz_color_filters", {}).items():

            color_hex = BZ_COLORS[cid]

            if cid == self.bz_active_color:

                btn.configure(fg_color=BZ_COLOR_ACTIVE[color_hex], text_color="#ffffff")

            else:

                btn.configure(fg_color=BZ_COLOR_LIGHT[color_hex], text_color=color_hex)



        self._update_bz_skill_tab()



    def _set_bz_type_filter(self, type_name):

        """Toggle type filter"""

        if getattr(self, "bz_active_type", None) == type_name:

            self.bz_active_type = None

        else:

            self.bz_active_type = type_name



        # Update button styles

        for tn, btn in getattr(self, "bz_type_filters", {}).items():

            if tn == self.bz_active_type:

                btn.configure(fg_color="#3a5a7a", text_color="#3b8ed0", border_color="#3b8ed0")

            else:

                btn.configure(fg_color="#2a2a4a", text_color="#888888", border_color="#444444")



        self._update_bz_skill_tab()



    def _clear_bz_filters(self):

        """Clear all filters"""

        self.bz_active_color = None

        self.bz_active_type = None

        if hasattr(self, "bz_search"):

            self.bz_search.delete(0, "end")



        BZ_COLORS = {2: "#ffcc00", 3: "#4488ff", 4: "#44cc44", 5: "#ff4444", 6: "#bb44ff", 7: "#333333", 0: "#aaaaaa"}

        BZ_COLOR_LIGHT = {"#ffcc00": "#4d3300", "#4488ff": "#0d1b33", "#44cc44": "#0d330d", "#ff4444": "#4d0d0d", "#bb44ff": "#2d0d4d", "#333333": "#0a0a0a", "#aaaaaa": "#222222"}

        for cid, btn in getattr(self, "bz_color_filters", {}).items():

            color_hex = BZ_COLORS[cid]

            btn.configure(fg_color=BZ_COLOR_LIGHT[color_hex], text_color=color_hex)



        for tn, btn in getattr(self, "bz_type_filters", {}).items():

            btn.configure(fg_color="#2a2a4a", text_color="#888888", border_color="#444444")



        self._update_bz_skill_tab()





    # Actions

    def _load_skill_icons(self):

        """加载技能图标映射表"""

        try:

            with open(os.path.join(os.path.dirname(__file__), "data", "skill_icons.json"), "r", encoding="utf-8") as f:

                return json.load(f)

        except Exception:

            return {}



    def _load_skill_descriptions(self):

        """加载技能描述映射表"""

        try:

            with open(os.path.join(os.path.dirname(__file__), "data", "bz_skill_desc.json"), "r", encoding="utf-8") as f:

                return json.load(f)

        except Exception:

            return {}



    def _ensure_skill_icon(self, skill_name, remote_url):

        """从远程URL下载技能图标到本地缓存"""

        import requests

        cache_dir = os.path.join(os.path.dirname(__file__), "data", "bz_cache", "icons")

        os.makedirs(cache_dir, exist_ok=True)

        local_path = os.path.join(cache_dir, f"{skill_name}.png")

        if os.path.exists(local_path):

            return local_path

        try:

            r = requests.get(remote_url, timeout=5)

            if r.status_code == 200:

                with open(local_path, "wb") as f:

                    f.write(r.content)

                return local_path

        except Exception:

            pass

        return None

    def fetch_bz(self):

        sel = self.tree.selection()

        if not sel:

            self.st.configure(text="请先选择角色")

            return

        name = self.tree.item(sel[0], "values")[0]

        self.st.configure(text=f"正在获取 {name}...")

        self.root.update()



        def do():

            d = self.mgr.fetch_baizhan_info(name)

            self.root.after(0, lambda: self._bz_done(name, d))



        threading.Thread(target=do, daemon=True).start()



    def _bz_done(self, name, d):

        if "error" in d:

            self.st.configure(text=f"{name}: {d['error']}")

            logger.warning(f"Fetch baizhan failed for {name}: {d['error']}")

        else:

            self.st.configure(text=f"{name}: 获取成功")

            logger.info(f"Baizhan data fetched for {name}")

            self._detail()

            self._update_bz_skill_tab(name)



    def enable_stats(self):

        sel = self.tree.selection()

        if not sel:

            self.st.configure(text="请先选择角色")

            return

        name = self.tree.item(sel[0], "values")[0]

        import tkinter.messagebox as mb

        if not mb.askyesno("确认", f"确定为 {name} 开启统计功能？"):

            return

        uid = None

        for d in os.listdir(self.mgr.my_data):

            if not d.endswith("@zhcn_hd"):

                continue

            ip = os.path.join(self.mgr.my_data, d, "info.jx3dat")

            if os.path.exists(ip):

                with open(ip, "rb") as f:

                    txt = f.read().decode("gbk", errors="replace")

                m = re.search(r'name="([^"]+)"', txt)

                if m and m.group(1) == name:

                    uid = d.split("@")[0]

                    break

        if not uid:

            self.st.configure(text="UID not found")

            logger.warning(f"UID not found for character {name}")

            return

        ok, msg = enable_all_stats(self.mgr.my_data, uid)

        self.st.configure(text=msg)

        logger.info(f"Enable stats for {name} (uid={uid}): {msg}")



    def export_json(self):

        p = self.mgr.export_json()

        self.st.configure(text=f"JSON: {p}")

        logger.info(f"Exported JSON: {p}")



    def configure_combat_logs(self):

        """一键为所有角色启用战斗日志（副本/秘境/战场/其他地图）"""

        import threading

        from combat_log_config import enable_combat_logs_for_all

        

        def run_config():

            self.st.configure(text="正在配置战斗日志设置...")

            data_path = self.mgr.my_data

            results = enable_combat_logs_for_all(data_path, dry_run=False)

            

            success_count = sum(1 for r in results if r["success"])

            total_count = len(results)

            updated_count = sum(len(r["updated"]) for r in results if r["success"])

            

            msg = f"完成: {success_count}/{total_count} 角色, 更新 {updated_count} 项设置"

            self.st.configure(text=msg)

            logger.info(msg)

        

        threading.Thread(target=run_config, daemon=True).start()



    def export_csv(self):

        p = os.path.join(os.path.dirname(__file__), "data", "export.csv")

        os.makedirs(os.path.dirname(p), exist_ok=True)

        with open(p, "w", encoding="utf-8-sig", newline="") as f:

            w = csv.writer(f)

            w.writerow(["Name", "Server", "School", "Level", "Equip", "Gold",

                         "Contribution", "Justice", "BZ_0-100", "BZ_Xiuluo"])

            for c in self.mgr.characters.values():

                prog = c.get("baizhan_progress", {})

                bz_k = prog.get("killed", "-") if prog else "-"

                bz_x = ("是" if prog.get("xiuluo") else "否") if prog else "-"

                w.writerow([c.get("name", ""),

                            f"{c.get('region', '')}/{c.get('server', '')}",

                            c.get("force_name", ""), c.get("level", ""),

                            c.get("equip_score", 0), c.get("gold", 0),

                            c.get("contribution", 0), c.get("justice", 0),

                            bz_k, bz_x])

        self.st.configure(text=f"CSV: {p}")

        logger.info(f"Exported CSV: {p}")



    def run(self):

        self.root.mainloop()





if __name__ == "__main__":

    App().run()
